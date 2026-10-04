// Production entry (`bun scripts/serve.ts`). SvelteKit 3 and @sveltejs/adapter-bun no longer read
// a runtime ORIGIN: the adapter takes the origin from configured protocol and host headers, or
// assumes https + Host. When the operator sets ORIGIN, this listener fronts the adapter over a
// private Unix socket and supplies the configured origin through headers only it can set. Without
// ORIGIN the adapter listens directly on HOST/PORT.
//
// This file runs from the image next to build/ without bundling: it imports only node: builtins
// and Bun globals.
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

type Environment = Record<string, string | undefined>;
type Log = Pick<Console, 'log' | 'warn'>;

export const PROTOCOL_HEADER = 'x-zondarr-origin-proto';
export const HOST_HEADER = 'x-zondarr-origin-host';
export const PEER_HEADER = 'x-zondarr-peer';

export const MISSING_ORIGIN_WARNING =
	'ORIGIN is not set: the server assumes https://<Host>. Plain-HTTP deployments must set ORIGIN ' +
	'(for example ORIGIN=http://192.168.1.10:3000), or same-origin writes are rejected with 403. ' +
	'Ignore this behind a TLS proxy that preserves Host.';

/**
 * Parses ORIGIN, which must be a bare http(s) origin (a trailing `/` is tolerated). The error
 * never echoes the value, which may carry credentials, and never wraps the URL parser's error
 * (Bun's ERR_INVALID_URL keeps the raw input).
 */
export function parseOrigin(value: string): URL {
	let url: URL | undefined;
	try {
		url = new URL(value);
	} catch {
		// fall through to the redacted error below
	}
	if (!url) throw new Error('ORIGIN must be a bare http(s) origin: it is not a valid URL.');
	if (url.protocol !== 'http:' && url.protocol !== 'https:') {
		throw new Error('ORIGIN must be a bare http(s) origin: the scheme must be http or https.');
	}
	if (url.username || url.password) {
		throw new Error('ORIGIN must be a bare http(s) origin: it contains credentials.');
	}
	if (url.origin !== value.replace(/\/$/, '')) {
		throw new Error(
			'ORIGIN must be a bare http(s) origin: remove any path, query, fragment or default port, ' +
				'and write the host in lowercase.'
		);
	}
	return url;
}

function integer(name: string, value: string, max: number): number {
	if (!/^\d+$/.test(value) || Number(value) > max) {
		throw new Error(`${name} must be an integer between 0 and ${max}.`);
	}
	return Number(value);
}

/** The adapter's SHUTDOWN_TIMEOUT, parsed as @sveltejs/adapter-bun parses it (default 30 s). */
export function shutdownTimeoutSeconds(environment: Environment): number {
	const value = environment.SHUTDOWN_TIMEOUT;
	return value !== undefined && /^\d+$/.test(value) ? Number(value) : 30;
}

/** The one startup warning (M10.2): only when neither ORIGIN nor PROTOCOL_HEADER is configured. */
export function missingOriginWarning(environment: Environment): string | null {
	return environment.ORIGIN || environment.PROTOCOL_HEADER ? null : MISSING_ORIGIN_WARNING;
}

export type Plan =
	| { mode: 'direct'; warning: string | null }
	| {
			mode: 'front';
			origin: URL;
			hostname: string;
			port: number;
			idleTimeout: number | undefined;
			ownPeerHeader: boolean;
			directory: string;
			socket: string;
	  };

/**
 * Prepares the environment the adapter reads and returns how to start. Mutates `environment`.
 */
export function prepare(environment: Environment): Plan {
	// @sveltejs/adapter-bun renamed IDLE_TIMEOUT to CONNECTION_IDLE_TIMEOUT; keep the old variable
	// working. An explicit CONNECTION_IDLE_TIMEOUT wins.
	if (environment.IDLE_TIMEOUT) environment.CONNECTION_IDLE_TIMEOUT ??= environment.IDLE_TIMEOUT;

	if (!environment.ORIGIN) {
		// The origin is never derived from the request's Host header here (DNS rebinding).
		return { mode: 'direct', warning: missingOriginWarning(environment) };
	}

	const origin = parseOrigin(environment.ORIGIN);
	const hostname = environment.HOST || '0.0.0.0';
	const port = integer('PORT', environment.PORT || '3000', 65535);
	const idle = environment.CONNECTION_IDLE_TIMEOUT;
	const idleTimeout = idle ? integer('CONNECTION_IDLE_TIMEOUT', idle, 255) : undefined;

	const directory = mkdtempSync(join(tmpdir(), 'zondarr-'));
	const socket = join(directory, 'app.sock');
	environment.SOCKET_PATH = socket;
	// The front overwrites these headers on every request, so clients cannot forge them, and
	// ORIGIN wins over any operator-configured protocol, host or port header.
	environment.PROTOCOL_HEADER = PROTOCOL_HEADER;
	environment.HOST_HEADER = HOST_HEADER;
	delete environment.PORT_HEADER;
	// An operator-configured address header (e.g. x-forwarded-for behind a trusted proxy) passes
	// through unchanged; otherwise the front reports the TCP peer itself.
	const ownPeerHeader = !environment.ADDRESS_HEADER;
	if (ownPeerHeader) environment.ADDRESS_HEADER = PEER_HEADER;
	// Over a Unix socket the adapter's event-stream idle exemption does not work (Bun 1.4.2,
	// oven-sh/bun#43816), so the adapter side never times out and the public listener enforces
	// the client idle timeout.
	environment.CONNECTION_IDLE_TIMEOUT = '0';

	return { mode: 'front', origin, hostname, port, idleTimeout, ownPeerHeader, directory, socket };
}

export async function serve(
	environment: Environment = process.env,
	importServer: () => Promise<unknown> = () =>
		import(pathToFileURL(resolve('build/index.js')).href),
	log: Log = console
): Promise<void> {
	const plan = prepare(environment);
	if (plan.mode === 'direct') {
		if (plan.warning) log.warn(plan.warning);
		await importServer();
		return;
	}

	const { origin, ownPeerHeader, directory, socket } = plan;
	const removeSocketDirectory = () => rmSync(directory, { recursive: true, force: true });
	let markReady = () => {};
	const ready = new Promise<void>((resolveReady) => {
		markReady = resolveReady;
	});

	// Bind the public port before loading the adapter, so a busy port never starts the app;
	// requests that arrive while the adapter loads wait for it.
	let listener: ReturnType<typeof Bun.serve>;
	try {
		listener = Bun.serve({
			hostname: plan.hostname,
			port: plan.port,
			...(plan.idleTimeout === undefined ? {} : { idleTimeout: plan.idleTimeout }),
			// BODY_SIZE_LIMIT is enforced by the adapter behind the socket.
			maxRequestBodySize: Number.MAX_SAFE_INTEGER,
			async fetch(request, server) {
				await ready;
				const url = new URL(request.url);
				const headers = new Headers(request.headers);
				headers.set(PROTOCOL_HEADER, origin.protocol.slice(0, -1));
				headers.set(HOST_HEADER, origin.host);
				if (ownPeerHeader) headers.set(PEER_HEADER, server.requestIP(request)?.address ?? '');
				else headers.delete(PEER_HEADER);
				let response: Response;
				try {
					response = await fetch(`http://localhost${url.pathname}${url.search}`, {
						method: request.method,
						headers,
						body: request.method === 'GET' || request.method === 'HEAD' ? null : request.body,
						redirect: 'manual',
						decompress: false,
						signal: request.signal,
						unix: socket
					});
				} catch {
					return new Response('Service Unavailable', { status: 503 });
				}
				if (response.headers.get('content-type')?.startsWith('text/event-stream')) {
					server.timeout(request, 0);
				}
				return response;
			}
		});
	} catch (error) {
		removeSocketDirectory();
		throw error;
	}

	// Shutdown: the adapter drains the socket side for up to SHUTDOWN_TIMEOUT, then emits
	// sveltekit:shutdown. A slow public client can still be downloading from this listener at
	// that point, so wait for the public drain too, within the same budget from the signal, and
	// force-close only when that deadline passes.
	let deadline = 0;
	let publicDrain: Promise<void> | undefined;
	const startDrain = () => {
		if (publicDrain) return publicDrain;
		deadline = Date.now() + shutdownTimeoutSeconds(environment) * 1000;
		publicDrain = listener.stop();
		return publicDrain;
	};
	// The adapter installs its own SIGTERM/SIGINT handlers only when it has finished loading. A
	// signal that arrives earlier is remembered and delivered again once they exist, so the
	// adapter still drains and emits sveltekit:shutdown. A second signal before then exits with
	// status 1, as the adapter does for a second signal. These handlers stay registered (never
	// the default handler, which would skip the cleanup below).
	let loaded = false;
	let earlySignal: NodeJS.Signals | undefined;
	const onSignal = (signal: NodeJS.Signals) => {
		startDrain();
		if (loaded) return;
		if (earlySignal) process.exit(1);
		earlySignal = signal;
	};
	process.on('SIGTERM', onSignal);
	process.on('SIGINT', onSignal);
	// Every exit, including the adapter's process.exit(1) on a second signal, removes the
	// socket directory (synchronously, as exit handlers must).
	process.once('exit', removeSocketDirectory);
	process.once('sveltekit:shutdown', async () => {
		const drain = startDrain();
		let timer: ReturnType<typeof setTimeout> | undefined;
		const drained = await Promise.race([
			drain.then(() => true),
			new Promise<false>((resolveTimeout) => {
				timer = setTimeout(() => resolveTimeout(false), Math.max(0, deadline - Date.now()));
			})
		]);
		clearTimeout(timer);
		if (!drained) await listener.stop(true);
		removeSocketDirectory();
	});

	try {
		await importServer();
	} catch (error) {
		await listener.stop(true);
		removeSocketDirectory();
		throw error;
	}
	loaded = true;
	markReady();
	if (earlySignal) process.kill(process.pid, earlySignal);

	log.log(`Listening on ${listener.url} for ${origin.origin}`);
}

if (import.meta.main) await serve();
