"""SQLite schema for large-scale hierarchy index."""

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    filepath TEXT NOT NULL UNIQUE,
    file_size INTEGER,
    last_modified TEXT
);

CREATE TABLE IF NOT EXISTS modules (
    id INTEGER PRIMARY KEY,
    module_name TEXT NOT NULL,
    module_ref TEXT NOT NULL UNIQUE,
    definition_file_id INTEGER NOT NULL,
    port_json TEXT,
    param_json TEXT,
    inst_json TEXT,
    module_kind TEXT DEFAULT 'module',
    FOREIGN KEY (definition_file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS instances (
    id INTEGER PRIMARY KEY,
    full_path TEXT NOT NULL,
    inst_leaf_name TEXT NOT NULL,
    module_id INTEGER NOT NULL,
    depth INTEGER NOT NULL,
    parent_path TEXT,
    filepath_id INTEGER,
    port_json TEXT,
    param_json TEXT,
    variant TEXT NOT NULL DEFAULT '',
    module_ref TEXT,
    FOREIGN KEY (module_id) REFERENCES modules(id),
    FOREIGN KEY (filepath_id) REFERENCES files(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_instances_variant_path ON instances(variant, full_path);
CREATE INDEX IF NOT EXISTS idx_instances_full_path ON instances(full_path);
CREATE INDEX IF NOT EXISTS idx_instances_name ON instances(inst_leaf_name);
CREATE INDEX IF NOT EXISTS idx_instances_module_id ON instances(module_id);
CREATE INDEX IF NOT EXISTS idx_instances_depth ON instances(depth);
CREATE INDEX IF NOT EXISTS idx_instances_parent_path ON instances(parent_path);
CREATE INDEX IF NOT EXISTS idx_instances_module_ref ON instances(module_ref);

CREATE TABLE IF NOT EXISTS instance_ports (
    id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL,
    port_name TEXT NOT NULL,
    FOREIGN KEY (instance_id) REFERENCES instances(id) ON DELETE CASCADE,
    UNIQUE(instance_id, port_name)
);

CREATE INDEX IF NOT EXISTS idx_instance_ports_name ON instance_ports(port_name);
CREATE INDEX IF NOT EXISTS idx_instance_ports_inst ON instance_ports(instance_id);

CREATE INDEX IF NOT EXISTS idx_modules_name ON modules(module_name);
CREATE INDEX IF NOT EXISTS idx_files_filepath ON files(filepath);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def create_database(conn) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()