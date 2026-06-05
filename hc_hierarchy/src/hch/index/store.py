"""SQLite bulk loader for FlatInstance rows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from hch.index.schema_sql import create_database
from hch.ingest.flatten_tags import apply_tags_dict_to_flat, flat_inst_tags_dict
from hch.schema import FlatInstance, InstanceEdge, ModuleRecord, PortRecord


class HierarchyStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        create_database(self.conn)
        self._migrate()

    def _migrate(self) -> None:
        cols = {
            r[1] for r in self.conn.execute("PRAGMA table_info(modules)").fetchall()
        }
        if "inst_json" not in cols:
            self.conn.execute("ALTER TABLE modules ADD COLUMN inst_json TEXT")
        if "module_kind" not in cols:
            self.conn.execute(
                "ALTER TABLE modules ADD COLUMN module_kind TEXT DEFAULT 'module'"
            )
        inst_cols = {
            r[1] for r in self.conn.execute("PRAGMA table_info(instances)").fetchall()
        }
        if "port_json" not in inst_cols:
            self.conn.execute("ALTER TABLE instances ADD COLUMN port_json TEXT")
        if "variant" not in inst_cols:
            self.conn.execute(
                "ALTER TABLE instances ADD COLUMN variant TEXT NOT NULL DEFAULT ''"
            )
        if "inst_tags_json" not in inst_cols:
            self.conn.execute("ALTER TABLE instances ADD COLUMN inst_tags_json TEXT")
        if "child_kind" not in inst_cols:
            self.conn.execute(
                "ALTER TABLE instances ADD COLUMN child_kind TEXT DEFAULT 'module'"
            )
        if "module_ref" not in inst_cols:
            self.conn.execute("ALTER TABLE instances ADD COLUMN module_ref TEXT")
            self.conn.execute(
                """
                UPDATE instances SET module_ref = (
                    SELECT m.module_ref FROM modules m
                    WHERE m.id = instances.module_id
                )
                WHERE module_ref IS NULL OR module_ref = ''
                """
            )
            self.conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_instances_module_ref
                ON instances(module_ref)
                """
            )
        if not self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_instances_variant_path'"
        ).fetchone():
            self.conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_instances_variant_path
                ON instances(variant, full_path)
                """
            )
        if not self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='instance_ports'"
        ).fetchone():
            self.conn.executescript(
                """
                CREATE TABLE instance_ports (
                    id INTEGER PRIMARY KEY,
                    instance_id INTEGER NOT NULL,
                    port_name TEXT NOT NULL,
                    FOREIGN KEY (instance_id) REFERENCES instances(id) ON DELETE CASCADE,
                    UNIQUE(instance_id, port_name)
                );
                CREATE INDEX idx_instance_ports_name ON instance_ports(port_name);
                CREATE INDEX idx_instance_ports_inst ON instance_ports(instance_id);
                """
            )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def _upsert_file(self, filepath: str) -> int:
        from hch.platform_paths import path_to_db

        fp = path_to_db(filepath) if filepath else filepath
        self.conn.execute(
            "INSERT OR IGNORE INTO files (filepath) VALUES (?)",
            (fp,),
        )
        row = self.conn.execute(
            "SELECT id FROM files WHERE filepath = ?",
            (fp,),
        ).fetchone()
        return int(row[0])

    def _module_inst_json(self, m: ModuleRecord) -> str:
        return json.dumps(
            [
                {
                    "inst": e.inst_name,
                    "child": e.child_module,
                    "parent": e.parent_module,
                    "file": e.file_path,
                    "params": e.param_overrides,
                    "in_generate": e.in_generate,
                    "via_bind": e.via_bind,
                    "from_macro": e.from_macro,
                    "generate_path": e.generate_path,
                    "bind_target_hier": e.bind_target_hier,
                    "port_connections": e.port_connections,
                    "child_type": e.child_type,
                    "child_kind": e.child_kind,
                    "unreachable": e.unreachable,
                    "generate_branch": e.generate_branch,
                }
                for e in m.instances
            ]
        )

    def load_modules(
        self,
        modules: Iterable[ModuleRecord],
        *,
        commit: bool = True,
        multi_def_paths_by_name: Optional[dict] = None,
    ) -> None:
        from hch.ingest.multi_def import expand_multi_def_module_records

        expanded = expand_multi_def_module_records(
            modules, extra_paths_by_name=multi_def_paths_by_name
        )
        for m in expanded:
            fid = self._upsert_file(m.file_path) if m.file_path else 0
            if not fid:
                self.conn.execute("INSERT OR IGNORE INTO files (filepath) VALUES ('')")
                fid = self.conn.execute(
                    "SELECT id FROM files WHERE filepath = ''"
                ).fetchone()[0]
            from hch.ingest.multi_def import module_ref as make_module_ref

            ref = make_module_ref(m.file_path, m.module_name)
            port_json = json.dumps(
                [{"name": p.name, "dir": p.direction, "type": p.type_str} for p in m.ports]
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO modules
                (module_name, module_ref, definition_file_id, port_json, param_json, inst_json, module_kind)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m.module_name,
                    ref,
                    fid,
                    port_json,
                    json.dumps(m.parameters),
                    self._module_inst_json(m),
                    m.module_kind or "module",
                ),
            )
        if commit:
            self.conn.commit()

    def load_all_modules(self) -> Dict[str, ModuleRecord]:
        out: Dict[str, ModuleRecord] = {}
        rows = self.conn.execute(
            """
            SELECT m.module_name, f.filepath, m.port_json, m.param_json, m.inst_json, m.module_kind
            FROM modules m
            LEFT JOIN files f ON f.id = m.definition_file_id
            """
        ).fetchall()
        for mname, fpath, port_json, param_json, inst_json, mkind in rows:
            ports = []
            if port_json:
                for p in json.loads(port_json):
                    ports.append(
                        PortRecord(
                            name=p.get("name", ""),
                            direction=p.get("dir", ""),
                            type_str=p.get("type", ""),
                        )
                    )
            params = json.loads(param_json) if param_json else {}
            instances = []
            if inst_json:
                for e in json.loads(inst_json):
                    instances.append(
                        InstanceEdge(
                            parent_module=e.get("parent", mname),
                            inst_name=e.get("inst", ""),
                            child_module=e.get("child", ""),
                            file_path=e.get("file", fpath or ""),
                            param_overrides=dict(e.get("params") or {}),
                            in_generate=bool(e.get("in_generate")),
                            unreachable=bool(e.get("unreachable")),
                            via_bind=bool(e.get("via_bind")),
                            from_macro=bool(e.get("from_macro")),
                            generate_path=str(e.get("generate_path") or ""),
                            bind_target_hier=str(e.get("bind_target_hier") or ""),
                            port_connections=dict(e.get("port_connections") or {}),
                            child_type=str(e.get("child_type") or ""),
                            child_kind=str(e.get("child_kind") or ""),
                            generate_branch=str(e.get("generate_branch") or ""),
                        )
                    )
            out[mname] = ModuleRecord(
                module_name=mname,
                file_path=fpath or "",
                ports=ports,
                parameters=params,
                instances=instances,
                module_kind=mkind or "module",
            )
        return out

    def clear_instances(self) -> None:
        self.conn.execute("DELETE FROM instance_ports")
        self.conn.execute("DELETE FROM instances")
        self.conn.commit()

    def _resolve_module_id(
        self,
        module_name: str,
        inst_file: str,
        parent_path: Optional[str],
        *,
        module_ref_hint: str = "",
    ) -> Optional[int]:
        from hch.ingest.instance_resolve import resolve_module_id

        return resolve_module_id(
            self.conn,
            module_name,
            module_ref_hint=module_ref_hint,
            inst_file=inst_file,
            parent_path=parent_path,
        )

    def load_instances(self, instances: Iterable[FlatInstance], *, commit: bool = True) -> None:
        for inst in instances:
            inst_ref = getattr(inst, "module_ref", None) or ""
            mod_id = self._resolve_module_id(
                inst.module,
                inst.file or "",
                inst.parent_path,
                module_ref_hint=inst_ref,
            )
            if mod_id is None:
                continue
            if not inst_ref:
                from hch.ingest.instance_resolve import module_ref_from_id

                inst_ref = module_ref_from_id(self.conn, mod_id)
            fid = self._upsert_file(inst.file) if inst.file else None
            port_json = json.dumps(inst.ports) if inst.ports else "[]"
            param_json = (
                json.dumps(inst.param_overrides) if inst.param_overrides else "{}"
            )
            variant = getattr(inst, "variant", "") or ""
            tags_json = json.dumps(flat_inst_tags_dict(inst))
            child_kind = getattr(inst, "child_kind", "") or "module"
            self.conn.execute(
                """
                INSERT OR REPLACE INTO instances
                (full_path, inst_leaf_name, module_id, depth, parent_path, filepath_id,
                 port_json, param_json, variant, inst_tags_json, child_kind, module_ref)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    inst.full_path,
                    inst.name,
                    mod_id,
                    inst.depth,
                    inst.parent_path,
                    fid,
                    port_json,
                    param_json,
                    variant,
                    tags_json,
                    child_kind,
                    inst_ref,
                ),
            )
            iid = self.conn.execute(
                "SELECT id FROM instances WHERE variant = ? AND full_path = ?",
                (variant, inst.full_path),
            ).fetchone()[0]
            self.conn.execute(
                "DELETE FROM instance_ports WHERE instance_id = ?",
                (iid,),
            )
            for pname in inst.ports:
                if pname:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO instance_ports (instance_id, port_name) VALUES (?, ?)",
                        (iid, pname),
                    )
        if commit:
            self.conn.commit()

    def set_meta(self, key: str, value: str, *, commit: bool = True) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            (key, value),
        )
        if commit:
            self.conn.commit()

    def count_instances(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM instances").fetchone()[0]

    def count_modules(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0]

    def export_instance_dicts(self) -> List[Dict[str, Any]]:
        """DQL/GUI-compatible instance list (name, module, file, ports, hierarchy)."""
        import sqlite3

        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            """
            SELECT i.full_path, i.inst_leaf_name, m.module_name, f.filepath,
                   i.depth, i.parent_path, i.port_json, i.inst_tags_json, i.child_kind,
                   COALESCE(i.module_ref, m.module_ref) AS module_ref
            FROM instances i
            JOIN modules m ON m.id = i.module_id
            LEFT JOIN files f ON f.id = i.filepath_id
            ORDER BY i.full_path
            """
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            ports_raw = r["port_json"]
            ports: List[str] = []
            if ports_raw:
                try:
                    loaded = json.loads(ports_raw)
                    if isinstance(loaded, list):
                        ports = [str(p) for p in loaded]
                except json.JSONDecodeError:
                    pass
            fp = r["filepath"] or ""
            entry: Dict[str, Any] = {
                "name": r["full_path"],
                "hierarchy": r["full_path"],
                "module": r["module_name"],
                "file": fp,
                "filepath": fp,
                "ports": ports,
                "depth": r["depth"],
                "parent": r["parent_path"],
                "child_kind": r["child_kind"] or "module",
                "module_ref": r["module_ref"] or "",
            }
            tags_raw = r["inst_tags_json"]
            if tags_raw:
                try:
                    tags = json.loads(tags_raw)
                    if isinstance(tags, dict):
                        entry.update(tags)
                except json.JSONDecodeError:
                    pass
            out.append(entry)
        return out

    def load_flat_instances(self) -> List[FlatInstance]:
        """Reload flat rows including inst_tags_json (E4 round-trip)."""
        import sqlite3

        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute(
            """
            SELECT i.full_path, i.inst_leaf_name, m.module_name, f.filepath,
                   i.depth, i.parent_path, i.port_json, i.param_json, i.variant,
                   i.inst_tags_json, i.child_kind,
                   COALESCE(i.module_ref, m.module_ref) AS module_ref
            FROM instances i
            JOIN modules m ON m.id = i.module_id
            LEFT JOIN files f ON f.id = i.filepath_id
            ORDER BY i.full_path
            """
        ).fetchall()
        out: List[FlatInstance] = []
        for r in rows:
            ports: List[str] = []
            if r["port_json"]:
                try:
                    loaded = json.loads(r["port_json"])
                    if isinstance(loaded, list):
                        ports = [str(p) for p in loaded]
                except json.JSONDecodeError:
                    pass
            params: Dict[str, str] = {}
            if r["param_json"]:
                try:
                    params = dict(json.loads(r["param_json"]))
                except json.JSONDecodeError:
                    pass
            row = FlatInstance(
                full_path=r["full_path"],
                name=r["inst_leaf_name"],
                module=r["module_name"],
                file=r["filepath"] or "",
                ports=ports,
                depth=int(r["depth"]),
                parent_path=r["parent_path"],
                param_overrides=params,
                child_kind=r["child_kind"] or "module",
                variant=r["variant"] or "",
                module_ref=r["module_ref"] or "",
            )
            if r["inst_tags_json"]:
                try:
                    apply_tags_dict_to_flat(row, json.loads(r["inst_tags_json"]))
                except json.JSONDecodeError:
                    pass
            out.append(row)
        return out