// @vitest-environment node
// scripts/serve.ts runs under Bun; these tests run on Node (Vitest). The pure parts are tested in
// process; the network behaviour is exercised by spawning `bun scripts/serve.ts` in a temporary
// directory whose build/index.js is a stand-in adapter (scripts/fixtures/standin-adapter.js).
import { type ChildProcess, spawn } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { request as httpRequest, type IncomingMessage } from 'node:http';
import { connect, createServer, type Server } from 'node:net';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	endQuietly,
	forwardPath,
	HOST_HEADER,
	MISSING_ORIGIN_WARNING,
	missingOriginWarning,
	ORIGIN_ERROR,
	PEER_HEADER,
	PROTOCOL_HEADER,
	parseOrigin,
	prepare,
	serve,
	shutdownTimeoutSeconds
} from './serve';

const SERVE = resolve(import.meta.dirname, 'serve.ts');
const STANDIN = resolve(import.meta.dirname, 'fixtures/standin-adapter.js');
const cleanups: (() => void)[] = [];

afterEach(() => {
	for (const cleanup of cleanups.splice(0)) cleanup();
});

function scratch(): string {
	const directory = mkdtempSync(join(tmpdir(), 'serve-test-'));
	cleanups.push(() => rmSync(directory, { recursive: true, force: true }));
	return directory;
}

async function freePort(): Promise<number> {
	const server = createServer();
	await new Promise<void>((done) => server.listen(0, '127.0.0.1', done));
	const { port } = server.address() as { port: number };
	await new Promise((done) => server.close(done));
	return port;
}

/** Fake credentials, built at runtime and never real. */
const fakeSecret = () => ['pw', 'fake', Math.random().toString(36).slice(2)].join('-');

type Started = {
	child: ChildProcess;
	port: number;
	temp: string;
	output: () => string;
	exited: Promise<{ code: number | null; signal: NodeJS.Signals | null }>;
};

/** Starts `bun scripts/serve.ts` with a private TMPDIR, so leftover socket directories show. */
async function start(env: Record<string, string>, { waitFor = 'ready' } = {}): Promise<Started> {
	const cwd = scratch();
	const temp = scratch();
	mkdirSync(join(cwd, 'build'));
	copyFileSync(STANDIN, join(cwd, 'build', 'index.js'));
	const port = env.PORT ? Number(env.PORT) : await freePort();
	const child = spawn('bun', [SERVE], {
		cwd,
		env: {
			PATH: process.env.PATH ?? '',
			HOME: process.env.HOME ?? '',
			TMPDIR: temp,
			HOST: '127.0.0.1',
			PORT: String(port),
			...env
		},
		stdio: ['ignore', 'pipe', 'pipe']
	});
	let output = '';
	child.stdout?.on('data', (chunk) => {
		output += chunk;
	});
	child.stderr?.on('data', (chunk) => {
		output += chunk;
	});
	const exited = new Promise<{ code: number | null; signal: NodeJS.Signals | null }>((done) =>
		child.on('exit', (code, signal) => done({ code, signal }))
	);
	cleanups.push(() => child.kill('SIGKILL'));
	if (waitFor === 'ready') {
		const deadline = Date.now() + 10_000;
		while (!/Listening on|standin listening on http/.test(output)) {
			if (Date.now() > deadline || child.exitCode !== null) {
				throw new Error(`serve.ts did not start:\n${output}`);
			}
			await new Promise((done) => setTimeout(done, 25));
		}
	}
	return { child, port, temp, output: () => output, exited };
}

type Reply = { status: number; headers: IncomingMessage['headers']; body: Buffer };

function call(
	port: number,
	path: string,
	options: { method?: string; headers?: Record<string, string>; body?: string } = {}
): Promise<Reply> {
	return new Promise((done, fail) => {
		const req = httpRequest(
			{ host: '127.0.0.1', port, path, method: options.method ?? 'GET', headers: options.headers },
			(res) => {
				const chunks: Buffer[] = [];
				res.on('data', (chunk: Buffer) => chunks.push(chunk));
				res.on('end', () =>
					done({ status: res.statusCode ?? 0, headers: res.headers, body: Buffer.concat(chunks) })
				);
				res.on('error', fail);
			}
		);
		req.on('error', fail);
		req.end(options.body);
	});
}

async function echo(port: number, options: Parameters<typeof call>[2] = {}) {
	const reply = await call(port, '/echo?x=1', options);
	return JSON.parse(reply.body.toString()) as {
		method: string;
		path: string;
		search: string;
		body: string;
		headers: Record<string, string>;
		env: Record<string, string | null>;
	};
}

/** A raw HTTP/1.1 request, so the Host header and the path are exactly what is written. */
function rawRequest(port: number, head: string): Promise<string> {
	return new Promise((done, fail) => {
		let received = '';
		const socket = connect(port, '127.0.0.1', () => {
			socket.write(`${head}\r\nConnection: close\r\n\r\n`);
		});
		socket.on('data', (chunk) => {
			received += chunk.toString();
		});
		socket.on('end', () => done(received));
		socket.on('error', fail);
	});
}

const socketDirectories = (temp: string) =>
	readdirSync(temp).filter((name) => name.startsWith('zondarr-'));

/** The exact texts of the shared origin contract (00-coordination 3.1), with Zondarr's name. */
const CONTRACT_ERROR =
	'ORIGIN must be a bare http(s) origin such as http://192.168.1.10:3000 (no path, query, fragment or credentials).';
const CONTRACT_WARNING =
	'ORIGIN is not set: Zondarr assumes it is served over HTTPS behind a proxy that preserves the Host header. Over plain HTTP, signing in and saving changes (including first-run setup) will fail. Set ORIGIN to the address users open, for example ORIGIN=http://192.168.1.10:3000.';

/** The message `parseOrigin` throws for `value`, or null when it accepts it. */
function parseError(value: string): string | null {
	try {
		parseOrigin(value);
		return null;
	} catch (error) {
		return (error as Error).message;
	}
}

describe('parseOrigin', () => {
	it('uses the contract texts', () => {
		expect(ORIGIN_ERROR).toBe(CONTRACT_ERROR);
		expect(MISSING_ORIGIN_WARNING).toBe(CONTRACT_WARNING);
	});

	it.each([
		'http://192.168.1.10:3000',
		'https://zondarr.example.com',
		'http://localhost:4173',
		'http://[::1]:3000',
		'https://zondarr.example.com:8443'
	])('accepts %s as it is', (value) => {
		expect(parseOrigin(value).origin).toBe(value);
	});

	it.each([
		['a trailing slash', 'http://localhost:4173/', 'http://localhost:4173'],
		['surrounding whitespace', '  https://zondarr.example.com \n', 'https://zondarr.example.com'],
		['an uppercase scheme and host', 'HTTP://Zondarr.Example:8080', 'http://zondarr.example:8080'],
		['a default port on http', 'http://zondarr.example:80', 'http://zondarr.example'],
		['a default port on https', 'https://zondarr.example:443', 'https://zondarr.example'],
		['an IDN host', 'http://bücher.example:3000', 'http://xn--bcher-kva.example:3000'],
		['all of them at once', ' HTTPS://ZONDARR.Example:443/ ', 'https://zondarr.example']
	])('normalizes %s to the canonical origin', (_case, value, canonical) => {
		expect(parseOrigin(value).origin).toBe(canonical);
	});

	it.each([
		['a path', 'http://example.com/app'],
		['two slashes', 'http://example.com//'],
		['a query', 'http://example.com/?a=1'],
		['an empty query', 'http://example.com?'],
		['a fragment', 'http://example.com/#top'],
		['an empty fragment', 'http://example.com#'],
		['a user name', 'http://user@example.com'],
		['a user name and password', 'http://user:pw@example.com'],
		['a non-http(s) scheme', 'ftp://example.com'],
		['garbage', 'not a url'],
		['an empty host', 'http://']
	])('rejects %s with exactly the contract error', (_reason, value) => {
		expect(parseError(value)).toBe(CONTRACT_ERROR);
	});

	it('never echoes the value, even when the URL parser rejects it', () => {
		const secret = fakeSecret();
		for (const value of [
			`http://user:${secret}@example.com`,
			`http://user:${secret}@example.com/x`,
			`http://user:${secret}@exa mple.com`,
			`http://example.com/${secret}`
		]) {
			let caught: unknown;
			try {
				parseOrigin(value);
			} catch (error) {
				caught = error;
			}
			expect(caught).toBeInstanceOf(Error);
			expect((caught as Error).message).toBe(CONTRACT_ERROR);
			expect((caught as Error).cause).toBeUndefined();
			expect(Object.keys(caught as object)).toEqual([]);
			expect(JSON.stringify(caught)).not.toContain(secret);
		}
	});
});

describe('missingOriginWarning (M10.2)', () => {
	it('warns when neither ORIGIN nor PROTOCOL_HEADER is set', () => {
		expect(missingOriginWarning({})).toBe(CONTRACT_WARNING);
		expect(missingOriginWarning({ ORIGIN: ' ', PROTOCOL_HEADER: '' })).toBe(CONTRACT_WARNING);
	});

	it.each([
		['ORIGIN', { ORIGIN: 'http://192.168.1.10:3000' }],
		['PROTOCOL_HEADER', { PROTOCOL_HEADER: 'x-forwarded-proto' }]
	])('does not warn when %s is set', (_name, environment) => {
		expect(missingOriginWarning(environment)).toBeNull();
	});
});

describe('prepare', () => {
	it('maps IDLE_TIMEOUT only when it is set, and an explicit CONNECTION_IDLE_TIMEOUT wins', () => {
		const mapped: Record<string, string | undefined> = { IDLE_TIMEOUT: '20' };
		prepare(mapped);
		expect(mapped.CONNECTION_IDLE_TIMEOUT).toBe('20');

		const explicit: Record<string, string | undefined> = {
			IDLE_TIMEOUT: '20',
			CONNECTION_IDLE_TIMEOUT: '5'
		};
		prepare(explicit);
		expect(explicit.CONNECTION_IDLE_TIMEOUT).toBe('5');
		expect(explicit.IDLE_TIMEOUT).toBe('20');

		const unset: Record<string, string | undefined> = {};
		prepare(unset);
		expect(unset).not.toHaveProperty('CONNECTION_IDLE_TIMEOUT');
	});

	it('without ORIGIN plans the adapter directly: no socket, no front headers', () => {
		const environment: Record<string, string | undefined> = { PORT: '3000' };
		expect(prepare(environment)).toEqual({ mode: 'direct', warning: MISSING_ORIGIN_WARNING });
		expect(environment).toEqual({ PORT: '3000' });

		expect(prepare({ PROTOCOL_HEADER: 'x-forwarded-proto' })).toEqual({
			mode: 'direct',
			warning: null
		});
	});

	it('treats a blank ORIGIN as unset', () => {
		const environment: Record<string, string | undefined> = { ORIGIN: '  ' };
		expect(prepare(environment)).toEqual({ mode: 'direct', warning: CONTRACT_WARNING });
		expect(environment).not.toHaveProperty('ORIGIN');
		expect(environment).not.toHaveProperty('SOCKET_PATH');
	});

	it('exports the canonical ORIGIN for the app', () => {
		const environment: Record<string, string | undefined> = {
			ORIGIN: ' HTTP://Zondarr.Example:80/ '
		};
		const plan = prepare(environment);
		if (plan.mode !== 'front') throw new Error('expected the front');
		cleanups.push(() => rmSync(plan.directory, { recursive: true, force: true }));
		expect(environment.ORIGIN).toBe('http://zondarr.example');
		expect(plan.origin.origin).toBe('http://zondarr.example');
	});

	it('with ORIGIN prepares a private socket and the front headers', () => {
		const environment: Record<string, string | undefined> = {
			ORIGIN: 'http://192.168.1.10:3000',
			IDLE_TIMEOUT: '15',
			PORT_HEADER: 'x-forwarded-port',
			PROTOCOL_HEADER: 'x-forwarded-proto',
			HOST_HEADER: 'x-forwarded-host'
		};
		const plan = prepare(environment);
		if (plan.mode !== 'front') throw new Error('expected the front');
		cleanups.push(() => rmSync(plan.directory, { recursive: true, force: true }));

		expect(plan.hostname).toBe('0.0.0.0');
		expect(plan.port).toBe(3000);
		expect(plan.idleTimeout).toBe(15);
		expect(plan.ownPeerHeader).toBe(true);
		expect(plan.directory.startsWith(join(tmpdir(), 'zondarr-'))).toBe(true);
		expect(existsSync(plan.directory)).toBe(true);
		expect(plan.socket).toBe(join(plan.directory, 'app.sock'));
		expect(environment.SOCKET_PATH).toBe(plan.socket);
		expect(environment.PROTOCOL_HEADER).toBe(PROTOCOL_HEADER);
		expect(environment.HOST_HEADER).toBe(HOST_HEADER);
		expect(environment.ADDRESS_HEADER).toBe(PEER_HEADER);
		expect(environment).not.toHaveProperty('PORT_HEADER');
		expect(environment.CONNECTION_IDLE_TIMEOUT).toBe('0');
	});

	it('keeps an operator ADDRESS_HEADER and leaves the idle default when none is set', () => {
		const environment: Record<string, string | undefined> = {
			ORIGIN: 'https://zondarr.example.com',
			ADDRESS_HEADER: 'x-forwarded-for'
		};
		const plan = prepare(environment);
		if (plan.mode !== 'front') throw new Error('expected the front');
		cleanups.push(() => rmSync(plan.directory, { recursive: true, force: true }));
		expect(plan.ownPeerHeader).toBe(false);
		expect(plan.idleTimeout).toBeUndefined();
		expect(environment.ADDRESS_HEADER).toBe('x-forwarded-for');
	});

	it.each([
		['PORT', { ORIGIN: 'http://a.example', PORT: 'http' }],
		['PORT', { ORIGIN: 'http://a.example', PORT: '70000' }],
		['CONNECTION_IDLE_TIMEOUT', { ORIGIN: 'http://a.example', CONNECTION_IDLE_TIMEOUT: '300' }],
		['ORIGIN', { ORIGIN: 'http://a.example/path' }]
	])('rejects an invalid %s before creating a socket directory', (name, environment) => {
		const before = readdirSync(tmpdir()).filter((entry) => entry.startsWith('zondarr-'));
		expect(() => prepare({ ...environment })).toThrow(new RegExp(`^${name} must be`));
		const after = readdirSync(tmpdir()).filter((entry) => entry.startsWith('zondarr-'));
		expect(after).toEqual(before);
	});

	it('reads SHUTDOWN_TIMEOUT as the adapter does', () => {
		expect(shutdownTimeoutSeconds({})).toBe(30);
		expect(shutdownTimeoutSeconds({ SHUTDOWN_TIMEOUT: '5' })).toBe(5);
		expect(shutdownTimeoutSeconds({ SHUTDOWN_TIMEOUT: 'soon' })).toBe(30);
	});
});

describe('forwardPath', () => {
	it.each([
		['http://x/_app/immutable/a%20b.js?v=%2F&q', '/_app/immutable/a%20b.js?v=%2F&q'],
		['http://x//double', '//double'],
		['http://x', '/'],
		['http://[::1/odd?host', '/odd?host'],
		['/relative?when=the+Host+is+unparseable', '/relative?when=the+Host+is+unparseable']
	])('forwards %s as %s', (requestUrl, path) => {
		expect(forwardPath(requestUrl)).toBe(path);
	});
});

describe('endQuietly', () => {
	it('passes chunks through and closes instead of erroring', async () => {
		let step = 0;
		const broken = new ReadableStream<Uint8Array>({
			pull(controller) {
				step++;
				if (step === 1) controller.enqueue(new TextEncoder().encode('data: one\n\n'));
				else controller.error(new Error('socket closed'));
			}
		});
		expect(await new Response(endQuietly(broken)).text()).toBe('data: one\n\n');
	});

	it('cancels the upstream when the client goes away', async () => {
		let cancelled = false;
		const upstream = new ReadableStream<Uint8Array>({
			pull(controller) {
				controller.enqueue(new TextEncoder().encode('.'));
			},
			cancel() {
				cancelled = true;
			}
		});
		const reader = endQuietly(upstream).getReader();
		await reader.read();
		await reader.cancel();
		expect(cancelled).toBe(true);
	});
});

describe('serve with injected dependencies', () => {
	it('without ORIGIN logs exactly one warning and imports the adapter directly', async () => {
		const log = { log: vi.fn(), warn: vi.fn() };
		const importServer = vi.fn(async () => {});
		const environment: Record<string, string | undefined> = {};
		await serve(environment, importServer, log);
		expect(log.warn).toHaveBeenCalledTimes(1);
		expect(log.warn).toHaveBeenCalledWith(MISSING_ORIGIN_WARNING);
		expect(importServer).toHaveBeenCalledOnce();
		expect(environment).not.toHaveProperty('SOCKET_PATH');
	});

	it('without ORIGIN but with PROTOCOL_HEADER logs no warning', async () => {
		const log = { log: vi.fn(), warn: vi.fn() };
		await serve({ PROTOCOL_HEADER: 'x-forwarded-proto' }, async () => {}, log);
		expect(log.warn).not.toHaveBeenCalled();
	});

	it('fails on a malformed ORIGIN before importing the adapter', async () => {
		const importServer = vi.fn(async () => {});
		await expect(serve({ ORIGIN: 'ftp://example.com' }, importServer, console)).rejects.toThrow(
			/^ORIGIN must be a bare http\(s\) origin/
		);
		expect(importServer).not.toHaveBeenCalled();
	});
});

describe('serve.ts process', () => {
	it('without ORIGIN loads the adapter directly and warns exactly once', async () => {
		const server = await start({});
		const seen = await echo(server.port);
		expect(seen.env).toMatchObject({ SOCKET_PATH: null, PROTOCOL_HEADER: null, HOST_HEADER: null });
		expect(server.output().split(MISSING_ORIGIN_WARNING).length - 1).toBe(1);
		expect(server.output()).not.toContain('Listening on http');
		expect(socketDirectories(server.temp)).toEqual([]);
	});

	it('does not warn when ORIGIN or PROTOCOL_HEADER is set', async () => {
		const withProtocol = await start({ PROTOCOL_HEADER: 'x-forwarded-proto' });
		await echo(withProtocol.port);
		expect(withProtocol.output()).not.toContain(MISSING_ORIGIN_WARNING);

		const port = await freePort();
		const fronted = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		await echo(fronted.port);
		expect(fronted.output()).not.toContain(MISSING_ORIGIN_WARNING);
	});

	it('with ORIGIN fronts the adapter and overwrites the origin and peer headers', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		expect(server.output()).toContain(`for http://127.0.0.1:${port}`);
		expect(socketDirectories(server.temp)).toHaveLength(1);

		const seen = await echo(server.port, {
			headers: {
				host: 'evil.example',
				[PROTOCOL_HEADER]: 'https',
				[HOST_HEADER]: 'evil.example',
				[PEER_HEADER]: '203.0.113.9',
				'x-forwarded-for': '203.0.113.9'
			}
		});
		expect(seen.env).toMatchObject({
			PROTOCOL_HEADER,
			HOST_HEADER,
			ADDRESS_HEADER: PEER_HEADER,
			PORT_HEADER: null,
			CONNECTION_IDLE_TIMEOUT: '0'
		});
		expect(seen.env.SOCKET_PATH).toMatch(/zondarr-[^/]+\/app\.sock$/);
		expect(seen.headers[PROTOCOL_HEADER]).toBe('http');
		expect(seen.headers[HOST_HEADER]).toBe(`127.0.0.1:${port}`);
		expect(seen.headers[PEER_HEADER]).toBe('127.0.0.1');
		// Forwarded headers pass through untouched; the adapter only trusts the ones it is told to.
		expect(seen.headers['x-forwarded-for']).toBe('203.0.113.9');
	});

	it('normalizes ORIGIN and the app reads the canonical value', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: ` HTTP://LocalHost:${port}/ `, PORT: String(port) });
		expect(server.output()).toContain(`for http://localhost:${port}`);
		const seen = await echo(server.port);
		expect(seen.env.ORIGIN).toBe(`http://localhost:${port}`);
		expect(seen.headers[PROTOCOL_HEADER]).toBe('http');
		expect(seen.headers[HOST_HEADER]).toBe(`localhost:${port}`);
	});

	it('passes an operator ADDRESS_HEADER through and drops a client-supplied peer header', async () => {
		const port = await freePort();
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			ADDRESS_HEADER: 'x-forwarded-for'
		});
		const seen = await echo(server.port, {
			headers: { [PEER_HEADER]: '203.0.113.9', 'x-forwarded-for': '198.51.100.7' }
		});
		expect(seen.env.ADDRESS_HEADER).toBe('x-forwarded-for');
		expect(seen.headers['x-forwarded-for']).toBe('198.51.100.7');
		expect(seen.headers).not.toHaveProperty(PEER_HEADER);
	});

	it('forwards method, path, query and body, sends no body for GET, and leaves redirects and encodings alone', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });

		const posted = await echo(server.port, { method: 'POST', body: 'hello' });
		expect(posted).toMatchObject({ method: 'POST', path: '/echo', search: '?x=1', body: 'hello' });
		const got = await echo(server.port, {
			method: 'GET',
			body: 'dropped',
			headers: { 'content-length': '7' }
		});
		expect(got).toMatchObject({ method: 'GET', body: '' });
		const head = await call(server.port, '/echo', { method: 'HEAD' });
		expect(head.status).toBe(200);
		expect(head.body.length).toBe(0);

		const redirect = await call(server.port, '/redirect');
		expect(redirect.status).toBe(302);
		expect(redirect.headers.location).toBe('/elsewhere');

		const gzip = await call(server.port, '/gzip', { headers: { 'accept-encoding': 'gzip' } });
		expect(gzip.headers['content-encoding']).toBe('gzip');
		expect(gzip.body.subarray(0, 2)).toEqual(Buffer.from([0x1f, 0x8b]));
	});

	it('forwards an encoded path and query byte for byte', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		const reply = await rawRequest(
			server.port,
			'GET /echo/caf%C3%A9%2Fx%20y?q=a%20b&r=%2F HTTP/1.1\r\nHost: anything'
		);
		expect(reply).toMatch(/^HTTP\/1\.1 200 /);
		const seen = JSON.parse(reply.slice(reply.indexOf('\r\n\r\n') + 4));
		expect(seen.url).toMatch(/^http:\/\/[^/]+\/echo\/caf%C3%A9%2Fx%20y\?q=a%20b&r=%2F$/);
	});

	// Bun builds request.url from the client's Host. The front must not parse it: it forwards the
	// request, and the adapter (here the stand-in, mirroring adapter-bun) answers with its own 400.
	it.each([
		['a Host the URL parser rejects', 'a b'],
		['an empty Host', ''],
		['an unclosed IPv6 Host', '[::1'],
		['a Host with a stray percent sign', 'ex%ample']
	])('forwards a request with %s instead of failing in the front', async (_case, host) => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		const reply = await rawRequest(server.port, `GET /echo?x=1 HTTP/1.1\r\nHost: ${host}`);
		expect(reply).toMatch(/^HTTP\/1\.1 400 /);
		expect(reply.slice(reply.indexOf('\r\n\r\n') + 4)).toBe('Bad Request');
		expect(server.output()).not.toMatch(/TypeError|Invalid URL/);
	});

	it('propagates a client abort to the adapter', async () => {
		const port = await freePort();
		const marker = join(scratch(), 'aborted');
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			STANDIN_ABORT_FILE: marker
		});
		await new Promise<void>((done) => {
			const req = httpRequest({ host: '127.0.0.1', port: server.port, path: '/hold' }, (res) => {
				res.once('data', () => {
					req.destroy();
					done();
				});
			});
			req.on('error', () => {});
			req.end();
		});
		await expect.poll(() => existsSync(marker), { timeout: 5000 }).toBe(true);
	});

	it('answers 503 when the adapter is unreachable', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		await call(server.port, '/stop');
		await new Promise((done) => setTimeout(done, 100));
		const reply = await call(server.port, '/echo');
		expect(reply.status).toBe(503);
	});

	it('keeps an idle event stream open past the client idle timeout', async () => {
		const port = await freePort();
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			IDLE_TIMEOUT: '1'
		});
		const reply = await call(server.port, '/sse?gap=2500');
		expect(reply.headers['content-type']).toBe('text/event-stream');
		expect(reply.body.toString()).toBe('data: one\n\ndata: two\n\n');
	}, 10_000);

	/** Reads a response to its end and reports how it ended: a clean end, or a reset mid-body. */
	function readToEnd(port: number, path: string) {
		return new Promise<{ body: string; outcome: 'complete' | 'incomplete' | 'error' }>((done) => {
			let body = '';
			let settled = false;
			// Node reports a reset on the request (ECONNRESET) before the response's aborted event,
			// after delivering any data received, so both paths settle with the body read so far.
			const finish = (outcome: 'complete' | 'incomplete' | 'error') => {
				if (settled) return;
				settled = true;
				done({ body, outcome });
			};
			const req = httpRequest({ host: '127.0.0.1', port, path }, (res) => {
				res.setEncoding('utf8');
				res.on('data', (chunk: string) => {
					body += chunk;
				});
				res.on('end', () => finish(res.complete ? 'complete' : 'incomplete'));
				res.on('aborted', () => finish('incomplete'));
				res.on('error', () => finish('error'));
			});
			req.on('error', () => finish('error'));
			req.end();
		});
	}

	it('ends a proxied event stream normally when the adapter breaks it off, without log noise', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		// A clean end of the public stream (not a reset), so EventSource just reconnects.
		expect(await readToEnd(server.port, '/sse-break')).toEqual({
			body: 'data: one\n\n',
			outcome: 'complete'
		});
		await new Promise((done) => setTimeout(done, 200));
		expect(server.output()).not.toMatch(/TypeError|closed unexpectedly/);
	}, 15_000);

	it('still breaks off any other response the adapter breaks off, so truncation shows', async () => {
		const port = await freePort();
		const server = await start({ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) });
		// A reset mid-body: never a clean end, and never a stall (that would hit the test timeout).
		const result = await readToEnd(server.port, '/download-break');
		expect(result.body).toBe('partial');
		expect(['incomplete', 'error']).toContain(result.outcome);
	}, 15_000);

	// This pins the outcome (a slow client still downloading when the adapter has drained and
	// emitted sveltekit:shutdown gets every byte; the front stops accepting and removes the
	// socket), not the mechanism: on Bun 1.4.2 the body may already be buffered in the front by
	// then (otpravkarr saw a force-closing front pass too). The deadline end of the budget is
	// pinned by the SHUTDOWN_TIMEOUT=3 test below.
	it('on SIGTERM stops accepting, a slow client still gets every byte, the socket is removed', async () => {
		const port = await freePort();
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			SHUTDOWN_TIMEOUT: '15'
		});
		expect(socketDirectories(server.temp)).toHaveLength(1);

		// Read about 2 MiB/s, so the 8 MiB body is still downloading when the adapter's side has
		// drained and emits sveltekit:shutdown. Bun answers a still-streaming proxied body with
		// chunked encoding, so the check is the byte count against the adapter's body size.
		const download = new Promise<{ bytes: number; complete: boolean; error?: unknown }>((done) => {
			const req = httpRequest({ host: '127.0.0.1', port: server.port, path: '/big' }, (res) => {
				let bytes = 0;
				res.on('data', (chunk: Buffer) => {
					bytes += chunk.length;
					res.pause();
					setTimeout(() => res.resume(), Math.ceil(chunk.length / 2048));
				});
				res.on('end', () => done({ bytes, complete: res.complete }));
				res.on('error', (error) => done({ bytes, complete: false, error }));
			});
			req.on('error', (error) => done({ bytes: 0, complete: false, error }));
			req.end();
		});
		await new Promise((done) => setTimeout(done, 300));
		server.child.kill('SIGTERM');

		await expect.poll(() => server.output(), { timeout: 5000 }).toContain('standin drained');
		await expect(call(server.port, '/echo')).rejects.toThrow();

		const result = await download;
		expect(result.error).toBeUndefined();
		expect(result.complete).toBe(true);
		expect(result.bytes).toBe(8 * 1024 * 1024);
		expect(await server.exited).toEqual({ code: 0, signal: null });
		expect(socketDirectories(server.temp)).toEqual([]);
	}, 30_000);

	it('force-closes a client that cannot finish within SHUTDOWN_TIMEOUT', async () => {
		const port = await freePort();
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			SHUTDOWN_TIMEOUT: '3'
		});
		const download = new Promise<number>((done) => {
			const req = httpRequest({ host: '127.0.0.1', port: server.port, path: '/big' }, (res) => {
				let bytes = 0;
				res.on('data', (chunk: Buffer) => {
					bytes += chunk.length;
					res.pause();
					setTimeout(() => res.resume(), 200);
				});
				res.on('end', () => done(bytes));
				res.on('error', () => done(bytes));
				res.on('close', () => done(bytes));
			});
			req.on('error', () => done(-1));
			req.end();
		});
		await new Promise((done) => setTimeout(done, 300));
		const signalled = Date.now();
		server.child.kill('SIGTERM');

		expect(await server.exited).toEqual({ code: 0, signal: null });
		const elapsed = (Date.now() - signalled) / 1000;
		expect(elapsed).toBeGreaterThanOrEqual(2.5);
		expect(elapsed).toBeLessThan(5);
		expect(await download).toBeLessThan(8 * 1024 * 1024);
		expect(socketDirectories(server.temp)).toEqual([]);
	}, 30_000);

	it('shuts down cleanly when SIGTERM arrives while the adapter is still loading', async () => {
		const port = await freePort();
		const server = await start(
			{ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port), STANDIN_LOAD_DELAY_MS: '1500' },
			{ waitFor: 'exit' }
		);
		// The public port is bound before the adapter loads: wait for a TCP connect (an HTTP
		// request would be held until the adapter is ready), then signal mid-load.
		const accepting = () =>
			new Promise<boolean>((done) => {
				const socket = connect(port, '127.0.0.1');
				socket.once('connect', () => {
					socket.destroy();
					done(true);
				});
				socket.once('error', () => done(false));
			});
		await expect.poll(accepting, { timeout: 5000, interval: 25 }).toBe(true);
		expect(server.output()).not.toContain('standin listening');
		server.child.kill('SIGTERM');
		const signalled = Date.now();
		const exited = await Promise.race([
			server.exited,
			new Promise<'timeout'>((done) => setTimeout(() => done('timeout'), 8000))
		]);
		expect(exited).toEqual({ code: 0, signal: null });
		expect(Date.now() - signalled).toBeLessThan(8000);
		expect(socketDirectories(server.temp)).toEqual([]);
	}, 20_000);

	it('exits 1 and leaves no socket directory on a second signal during adapter load', async () => {
		const port = await freePort();
		const server = await start(
			{ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port), STANDIN_LOAD_DELAY_MS: '3000' },
			{ waitFor: 'exit' }
		);
		const accepting = () =>
			new Promise<boolean>((done) => {
				const socket = connect(port, '127.0.0.1');
				socket.once('connect', () => {
					socket.destroy();
					done(true);
				});
				socket.once('error', () => done(false));
			});
		await expect.poll(accepting, { timeout: 5000, interval: 25 }).toBe(true);
		expect(socketDirectories(server.temp)).toHaveLength(1);
		server.child.kill('SIGTERM');
		await new Promise((done) => setTimeout(done, 200));
		server.child.kill('SIGTERM');
		expect(await server.exited).toEqual({ code: 1, signal: null });
		expect(server.output()).not.toContain('standin listening');
		expect(socketDirectories(server.temp)).toEqual([]);
	}, 20_000);

	it('removes the socket directory when a second signal forces the exit after loading', async () => {
		const port = await freePort();
		const server = await start({
			ORIGIN: `http://127.0.0.1:${port}`,
			PORT: String(port),
			SHUTDOWN_TIMEOUT: '30'
		});
		// Keep a request in flight so the first signal starts a drain that does not finish.
		const held = new Promise<void>((done) => {
			const req = httpRequest({ host: '127.0.0.1', port: server.port, path: '/hold' }, (res) => {
				res.once('data', () => done());
				res.on('error', () => {});
			});
			req.on('error', () => {});
			req.end();
		});
		await held;
		expect(socketDirectories(server.temp)).toHaveLength(1);
		server.child.kill('SIGTERM');
		await new Promise((done) => setTimeout(done, 300));
		server.child.kill('SIGTERM');
		expect(await server.exited).toEqual({ code: 1, signal: null });
		expect(socketDirectories(server.temp)).toEqual([]);
	}, 20_000);

	it('leaves nothing behind when the adapter fails to load', async () => {
		const port = await freePort();
		const server = await start(
			{ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port), STANDIN_THROW: '1' },
			{ waitFor: 'exit' }
		);
		const { code } = await server.exited;
		expect(code).not.toBe(0);
		expect(server.output()).toContain('stand-in adapter failed to load');
		expect(socketDirectories(server.temp)).toEqual([]);
		const probe: Server = createServer();
		await new Promise<void>((done, fail) => {
			probe.once('error', fail);
			probe.listen(port, '127.0.0.1', done);
		});
		await new Promise((done) => probe.close(done));
	});

	it('fails clearly when the public port is taken, without starting the adapter', async () => {
		const blocker: Server = createServer();
		await new Promise<void>((done) => blocker.listen(0, '127.0.0.1', done));
		cleanups.push(() => blocker.close());
		const { port } = blocker.address() as { port: number };

		const server = await start(
			{ ORIGIN: `http://127.0.0.1:${port}`, PORT: String(port) },
			{ waitFor: 'exit' }
		);
		const { code } = await server.exited;
		expect(code).not.toBe(0);
		expect(server.output()).toMatch(/EADDRINUSE|address already in use|port \d+ in use/i);
		expect(server.output()).not.toContain('standin listening');
		expect(socketDirectories(server.temp)).toEqual([]);
	});

	it.each([
		['credentials', (secret: string) => `http://user:${secret}@zondarr.example.com`],
		['a value the URL parser rejects', (secret: string) => `http://user:${secret}@exa mple.com`],
		['a path', (secret: string) => `http://zondarr.example.com/${secret}`],
		['a query', (secret: string) => `http://zondarr.example.com/?${secret}`]
	])('fails clearly on a malformed ORIGIN (%s) without echoing it', async (_case, build) => {
		const secret = fakeSecret();
		const server = await start({ ORIGIN: build(secret) }, { waitFor: 'exit' });
		const { code } = await server.exited;
		expect(code).not.toBe(0);
		expect(server.output()).toContain(CONTRACT_ERROR);
		expect(server.output()).not.toContain(secret);
		expect(server.output()).not.toContain('standin listening');
		expect(socketDirectories(server.temp)).toEqual([]);
	});
});
