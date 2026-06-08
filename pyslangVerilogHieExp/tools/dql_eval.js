#!/usr/bin/env node
/**
 * Standalone DQL evaluator using the exact same parser as the HTML explorer.
 * Usage:
 *   node tools/dql_eval.js --query 'module in ("uart", "spi")' --data demo_data/instances.json
 *   node tools/dql_eval.js --query '...' --data data.json --format json
 */

const fs = require('fs');
const path = require('path');
const { matchesDQL } = require('./dql_parser.js');

function parseArgs() {
    const args = process.argv.slice(2);
    const result = {};
    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--query' || args[i] === '-q') {
            result.query = args[++i];
        } else if (args[i] === '--data' || args[i] === '-d') {
            result.dataPath = args[++i];
        } else if (args[i] === '--format' || args[i] === '-f') {
            result.format = args[++i];
        }
    }
    return result;
}

function main() {
    const args = parseArgs();

    if (!args.query) {
        console.error('Error: --query is required');
        process.exit(1);
    }

    let instances = [];
    if (args.dataPath) {
        const fullPath = path.resolve(args.dataPath);
        instances = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
    } else {
        // Default to demo data if not provided
        const defaultPath = path.join(__dirname, '..', 'demo_data', 'instances.json');
        if (fs.existsSync(defaultPath)) {
            instances = JSON.parse(fs.readFileSync(defaultPath, 'utf8'));
        }
    }

    const results = instances.filter(inst => {
        const ports = inst.ports || inst.port || null;
        return matchesDQL(args.query, inst.name || '', inst.module || '', ports, inst.filepath || '');
    });

    if (args.format === 'json') {
        console.log(JSON.stringify(results, null, 2));
    } else {
        // Simple YAML-like output
        console.log(`# DQL: ${args.query}`);
        console.log(`# Total: ${results.length} items\n`);
        results.forEach(item => {
            console.log(`- name: ${item.name}`);
            console.log(`  module: ${item.module}`);
            console.log(`  filepath: ${item.filepath || ''}`);
            if (item.ports) {
                console.log(`  ports: ${JSON.stringify(item.ports)}`);
            }
        });
    }
}

main();