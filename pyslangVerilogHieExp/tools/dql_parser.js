// ============================================================
// Standalone DQL Parser (extracted from hierarchy_explorer.html)
// Supports full Jira-style DQL with parentheses, AND/OR/NOT, ~ !~ in/not in, wildcards
// ============================================================

function matchesDQL(query, name, moduleName, ports, filepath) {
    const q = query.trim();
    if (!q) return true;

    const portNames = getPortNames(ports);
    const context = { name, moduleName, ports: portNames, filepath };

    try {
        const tokens = tokenizeDQL(q);
        const ast = parseDQL(tokens);
        return evaluateDQL(ast, context);
    } catch (e) {
        console.warn("DQL parse error:", e.message);
        return oldSimpleMatchesDQL(q, name, portNames, filepath);
    }
}

function getPortNames(p) {
    if (!p) return [];
    if (Array.isArray(p)) return p.map(x => String(x));
    if (typeof p === 'object') return Object.keys(p);
    return [];
}

// ---------------------- Tokenizer ----------------------
function tokenizeDQL(query) {
    const tokens = [];
    let i = 0;
    const s = query;

    const keywords = /^(AND|OR|NOT|IN|NOT\s+IN)\b/i;

    while (i < s.length) {
        if (/\s/.test(s[i])) { i++; continue; }

        if (s[i] === '(') { tokens.push({ type: 'LPAREN' }); i++; continue; }
        if (s[i] === ')') { tokens.push({ type: 'RPAREN' }); i++; continue; }

        if (s[i] === '"' || s[i] === "'") {
            const quote = s[i];
            let j = i + 1;
            let value = '';
            while (j < s.length && s[j] !== quote) {
                if (s[j] === '\\' && j + 1 < s.length) {
                    value += s[j + 1];
                    j += 2;
                } else {
                    value += s[j];
                    j++;
                }
            }
            if (j >= s.length) throw new Error("Unterminated string");
            tokens.push({ type: 'STRING', value });
            i = j + 1;
            continue;
        }

        if (s[i] === ',') { tokens.push({ type: 'COMMA' }); i++; continue; }
        if (s[i] === '[') { tokens.push({ type: 'LBRACKET' }); i++; continue; }
        if (s[i] === ']') { tokens.push({ type: 'RBRACKET' }); i++; continue; }

        const rest = s.slice(i);

        const notInMatch = rest.match(/^not\s+in\b/i);
        if (notInMatch) {
            tokens.push({ type: 'NOT_IN' });
            i += notInMatch[0].length;
            continue;
        }

        const kwMatch = rest.match(keywords);
        if (kwMatch) {
            const word = kwMatch[0].toUpperCase().replace(/\s+/g, '_');
            tokens.push({ type: word });
            i += kwMatch[0].length;
            continue;
        }

        if (rest.match(/^(!~|~|!=|<=|>=|!in|in|!=|=|>|<)/i)) {
            const opMatch = rest.match(/^(!~|~|!=|!in|in|<=|>=|!=|=|>|<)/i);
            let op = opMatch[0].toUpperCase();
            if (op === '!IN') op = 'NOT_IN';
            tokens.push({ type: 'OPERATOR', value: op });
            i += opMatch[0].length;
            continue;
        }

        const idMatch = rest.match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
        if (idMatch) {
            tokens.push({ type: 'IDENT', value: idMatch[0].toLowerCase() });
            i += idMatch[0].length;
            continue;
        }

        throw new Error(`Unexpected character at position ${i}: ${s[i]}`);
    }

    tokens.push({ type: 'EOF' });
    return tokens;
}

// ---------------------- Parser ----------------------
function parseDQL(tokens) {
    let pos = 0;

    function peek() { return tokens[pos]; }
    function consume(type) {
        if (peek().type === type) return tokens[pos++];
        throw new Error(`Expected ${type}, got ${peek().type}`);
    }

    function parseExpr() { return parseOr(); }

    function parseOr() {
        let node = parseAnd();
        while (peek().type === 'OR') {
            consume('OR');
            node = { type: 'OR', left: node, right: parseAnd() };
        }
        return node;
    }

    function parseAnd() {
        let node = parseNot();
        while (peek().type === 'AND') {
            consume('AND');
            node = { type: 'AND', left: node, right: parseNot() };
        }
        return node;
    }

    function parseNot() {
        if (peek().type === 'NOT') {
            consume('NOT');
            return { type: 'NOT', expr: parseNot() };
        }
        return parsePrimary();
    }

    function parsePrimary() {
        if (peek().type === 'LPAREN') {
            consume('LPAREN');
            const expr = parseExpr();
            consume('RPAREN');
            return expr;
        }
        return parseCondition();
    }

    function parseCondition() {
        const ident = consume('IDENT').value;
        const tok = peek();

        if (tok.type === 'IN' || tok.type === 'NOT_IN') {
            const isNot = tok.type === 'NOT_IN';
            consume(tok.type);

            let listTok;
            if (peek().type === 'LPAREN') {
                consume('LPAREN');
                listTok = 'RPAREN';
            } else if (peek().type === 'LBRACKET') {
                consume('LBRACKET');
                listTok = 'RBRACKET';
            } else {
                throw new Error("Expected ( or [ after IN");
            }

            const values = [];
            if (peek().type !== listTok) {
                values.push(parseValue());
                while (peek().type === 'COMMA') {
                    consume('COMMA');
                    values.push(parseValue());
                }
            }
            consume(listTok);
            return { type: 'IN', field: ident, values, negated: isNot };
        }

        if (tok.type === 'OPERATOR') {
            const op = consume('OPERATOR').value;
            const value = parseValue();
            return { type: 'COMPARE', field: ident, op, value };
        }

        throw new Error(`Unexpected token after field '${ident}'`);
    }

    function parseValue() {
        const t = peek();
        if (t.type === 'STRING') return { type: 'STRING', value: consume('STRING').value };
        if (t.type === 'IDENT') return { type: 'STRING', value: consume('IDENT').value };
        throw new Error(`Expected value, got ${t.type}`);
    }

    const ast = parseExpr();
    if (peek().type !== 'EOF') throw new Error("Unexpected tokens after expression");
    return ast;
}

// ---------------------- Evaluator ----------------------
function evaluateDQL(node, ctx) {
    if (!node) return false;

    switch (node.type) {
        case 'AND':
            return evaluateDQL(node.left, ctx) && evaluateDQL(node.right, ctx);
        case 'OR':
            return evaluateDQL(node.left, ctx) || evaluateDQL(node.right, ctx);
        case 'NOT':
            return !evaluateDQL(node.expr, ctx);
        case 'COMPARE': {
            const fieldValue = getFieldValue(node.field, ctx);
            const matched = matchPatternForField(node.field, fieldValue, node.value.value, ctx);
            const op = node.op;
            if (op === '~' || op === '=') return matched;
            if (op === '!~' || op === '!=') return !matched;
            return false;
        }
        case 'IN': {
            const fieldValue = getFieldValue(node.field, ctx);
            const any = node.values.some(v => matchPatternForField(node.field, fieldValue, v.value, ctx));
            return node.negated ? !any : any;
        }
        default:
            return false;
    }
}

function getFieldValue(field, ctx) {
    if (field === 'module' || field === 'modulename' || field === 'name') return ctx.name;
    if (field === 'file') return ctx.filepath || '';
    if (field === 'port' || field === 'ports') return ctx.ports;
    return '';
}

function matchPatternForField(field, fieldValue, pattern, ctx) {
    if (field === 'port' || field === 'ports') {
        const ports = Array.isArray(fieldValue) ? fieldValue : [];
        return ports.some(p => matchPattern(p, pattern));
    }
    return matchPattern(fieldValue, pattern);
}

function matchPattern(text, pattern) {
    if (!pattern) return true;
    const t = String(text || '').toLowerCase();
    const p = String(pattern).toLowerCase();

    if (!p.includes('*')) {
        return t.includes(p);
    }

    const escaped = p.replace(/[.+^${}()|[\]\\]/g, '\\$&');
    const regexStr = escaped.replace(/\*/g, '.*');
    try {
        return new RegExp(regexStr).test(t);
    } catch {
        return t.includes(p.replace(/\*/g, ''));
    }
}

function oldSimpleMatchesDQL(q, name, portNames, filepath) {
    const orParts = q.split(/\s+or\s+/i);
    return orParts.some(orPart => {
        const andParts = orPart.split(/\s+and\s+/i);
        return andParts.every(part => {
            part = part.trim();
            if (/^not\s+/i.test(part)) part = part.replace(/^not\s+/i, '').trim();

            let m = part.match(/module(?:name)?\s*(!~|~)\s*"([^"]*)"/i);
            if (m) {
                const neg = m[1] === '!~';
                const ok = matchPattern(name, m[2]);
                return neg ? !ok : ok;
            }

            m = part.match(/ports?\s*(!~|~)\s*"([^"]*)"/i);
            if (m) {
                const neg = m[1] === '!~';
                const ok = portNames.some(p => matchPattern(p, m[2]));
                return neg ? !ok : ok;
            }

            if (part) {
                const pat = part.replace(/^"|"$/g, '');
                return matchPattern(name, pat);
            }
            return false;
        });
    });
}

// Export for Node
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        matchesDQL,
        tokenizeDQL,
        parseDQL,
        evaluateDQL
    };
}