#!/usr/bin/env node
// rc - validate, compile and inspect RemoteCompose JSON without a browser.
//
//   node tools/rc.mjs validate doc.json
//   node tools/rc.mjs compile  doc.json [out.rc]
//   node tools/rc.mjs inspect  doc.json
//   node tools/rc.mjs encode   doc.json          # a #doc= fragment, gzipped
//
// The playground's "no install, no shell" claim only holds for an agent that can run
// JavaScript in a page. An agent that can only fetch cannot use it at all - the #doc=
// fragment never reaches a server. This gives that agent the same validate/compile loop at
// the command line, from the same bundled converter the page uses, so the two cannot
// disagree. Node only; no npm install.
//
// Output is JSON on stdout and the exit code is 0 for valid, 1 for invalid, 2 for usage.

import { readFileSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { createContext, runInContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const BUNDLE = resolve(here, '..', 'assets', 'json2rc.js');

// The bundle is an IIFE that assigns a global, so it is run in a context rather than
// imported. TextEncoder/TextDecoder are supplied because the bundle expects the browser's.
function loadConverter() {
    const ctx = createContext({ TextEncoder, TextDecoder, console });
    runInContext(readFileSync(BUNDLE, 'utf8'), ctx);
    if (!ctx.J2RC || typeof ctx.J2RC.convert !== 'function') {
        throw new Error(`could not load the converter from ${BUNDLE}`);
    }
    return ctx.J2RC;
}

const NOT_AN_OP = new Set(['header', 'root', 'modifiers', 'commands', 'content', 'type',
                           'variables', 'resources', 'bitmaps', 'shaders']);

function inspectDoc(doc) {
    const ops = {};
    const walk = (node) => {
        if (!node || typeof node !== 'object') return;
        if (Array.isArray(node)) return node.forEach(walk);
        for (const [k, v] of Object.entries(node)) {
            if (k === 'type' && typeof v === 'string') ops[v] = (ops[v] || 0) + 1;
            else if (!NOT_AN_OP.has(k) && v && typeof v === 'object' && !Array.isArray(v)
                     && /^[a-z]/.test(k)) ops[k] = (ops[k] || 0) + 1;
            walk(v);
        }
    };
    walk(doc);
    return { operations: ops, operationCount: Object.values(ops).reduce((a, b) => a + b, 0) };
}

function run() {
    const [cmd, file, out] = process.argv.slice(2);
    if (!cmd || !file) {
        console.error('usage: rc.mjs <validate|compile|inspect|encode> <doc.json> [out.rc]');
        process.exit(2);
    }
    const text = readFileSync(file, 'utf8');

    let doc;
    try {
        doc = JSON.parse(text);
    } catch (e) {
        console.log(JSON.stringify({ valid: false, stage: 'parse', errors: [
            { code: 'PG1001', path: '', message: e.message }] }, null, 2));
        process.exit(1);
    }

    if (cmd === 'encode') {
        // gzip then base64url: the playground sniffs the magic bytes, and uncompressed
        // base64 of a real document runs to thousands of characters.
        const b = gzipSync(Buffer.from(text, 'utf8')).toString('base64')
            .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        console.log(JSON.stringify({
            fragment: `#doc=${b}`,
            chars: b.length,
            uncompressedChars: Buffer.from(text, 'utf8').toString('base64').length,
        }, null, 2));
        return;
    }

    const J2RC = loadConverter();
    let bytes = null, error = null;
    try {
        bytes = J2RC.convert(text);
    } catch (e) {
        const name = (String(e.message).match(/'([^']+)'/) || [])[1];
        error = {
            code: e.name === 'NotImplementedComponent' ? 'PG1030' : 'PG1031',
            message: e.message,
            operation: name,
        };
    }

    // A {name, description, json} wrapper is unwrapped by the converter, so inspection has
    // to do the same or it reports null dimensions for 21 corpus documents.
    const inner = (doc && !doc.header && doc.json && typeof doc.json === 'object')
        ? doc.json : doc;
    const h = (inner && inner.header) || {};
    const base = {
        valid: !error, width: h.width ?? null, height: h.height ?? null,
        ...inspectDoc(inner),
        bytes: bytes ? bytes.length : null,
        errors: error ? [error] : [],
    };

    if (cmd === 'compile' && bytes) {
        const dest = out || file.replace(/\.json$/i, '.rc');
        writeFileSync(dest, Buffer.from(bytes));
        base.output = dest;
    }
    console.log(JSON.stringify(base, null, 2));
    process.exit(error ? 1 : 0);
}

run();
