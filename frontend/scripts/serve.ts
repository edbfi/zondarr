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

/** The startup error for a malformed ORIGIN (the shared origin contract); it never echoes the value. */
export const ORIGIN_ERROR =
	'ORIGIN must be a bare http(s) origin such as http://192.168.1.10:3000 (no path, query, fragment or credentials).';

/** The one startup warning without ORIGIN or PROTOCOL_HEADER (the shared origin contract). */
export const MISSING_ORIGIN_WARNING =
	'ORIGIN is not set: Zondarr assumes it is served over HTTPS behind a proxy that preserves the ' +
	'Host header. Over plain HTTP, signing in and saving changes (including first-run setup) will ' +
	'fail. Set ORIGIN to the address users open, for example ORIGIN=http://192.168.1.10:3000.';

/** A variable's value with surrounding whitespace removed; empty means unset. */
function setting(value: string | undefined): string | undefined {
	return value?.trim() || undefined;
}

/**
 * Parses ORIGIN as the shared origin contract says: trimmed, an http(s) URL with no credentials,
 * no path but `/` and no `?` or `#`. The returned URL's `origin` is the canonical value (lowercase
 * scheme and host, default port dropped, IDN as punycode, no trailing `/`). The error never echoes
 * the value, which may carry credentials, and never wraps the URL parser's error (Bun's
 * ERR_INVALID_URL keeps the raw input).
 */
export function parseOrigin(value: string): URL {
	const trimmed = value.trim();
	let url: URL | undefined;
	try {
		url = new URL(trimmed);
	} catch {
		// fall through to the redacted error below
	}
	if (
		!url ||
		(url.protocol !== 'http:' && url.protocol !== 'https:') ||
		url.username ||
		url.password ||
		url.pathname !== '/' ||
		/[?#]/.test(trimmed)
	) {
		throw new Error(ORIGIN_ERROR);
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
	return setting(environment.ORIGIN) || setting(environment.PROTOCOL_HEADER)
		? null
		: MISSING_ORIGIN_WARNING;
}

/**
 * The path and query of a request, exactly as Bun received them: sliced from `request.url` after
 * any authority, never re-parsed with `new URL()`, which throws when the client's Host header does
 * not parse (Bun then gives a relative `request.url`).
 */
export function forwardPath(requestUrl: string): string {
	// Already a bare path (the Host did not parse): forward it whole, even when its query holds
	// a URL with "://".
	if (requestUrl.startsWith('/')) return requestUrl;
	const scheme = requestUrl.indexOf('://');
	const start = scheme === -1 ? 0 : requestUrl.indexOf('/', scheme + 3);
	return start === -1 ? '/' : requestUrl.slice(start);
}

/**
 * An event-stream body that ends normally when the adapter breaks it off.
 *
 * At the end of its shutdown drain the adapter force-closes the event streams still open. Passed
 * through as is, that failure would reset the public connection too (browsers report a connection
 * reset, and Bun logs a TypeError); ending the stream instead lets EventSource reconnect as after
 * any end of stream. Only event streams get this: they have no length, so nothing looks complete
 * that is not. Other responses keep the error, so a truncated download stays visible. A client
 * that goes away still cancels the upstream.
 */
export function endQuietly(body: ReadableStream<Uint8Array>): ReadableStream<Uint8Array> {
	const reader = body.getReader();
	return new ReadableStream<Uint8Array>({
		async pull(controller) {
			try {
				const { done, value } = await reader.read();
				if (done) controller.close();
				else controller.enqueue(value);
			} catch {
				controller.close();
			}
		},
		cancel(reason) {
			return reader.cancel(reason);
		}
	});
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

	const configured = setting(environment.ORIGIN);
	if (!configured) {
		// A blank ORIGIN is unset. The origin is never derived from the request's Host header
		// here (DNS rebinding).
		delete environment.ORIGIN;
		return { mode: 'direct', warning: missingOriginWarning(environment) };
	}

	const origin = parseOrigin(configured);
	// The app reads the same canonical string the front supplies.
	environment.ORIGIN = origin.origin;
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
				const headers = new Headers(request.headers);
				headers.set(PROTOCOL_HEADER, origin.protocol.slice(0, -1));
				headers.set(HOST_HEADER, origin.host);
				if (ownPeerHeader) headers.set(PEER_HEADER, server.requestIP(request)?.address ?? '');
				else headers.delete(PEER_HEADER);
				let response: Response;
				try {
					response = await fetch(`http://localhost${forwardPath(request.url)}`, {
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
				if (
					response.headers.get('content-type')?.startsWith('text/event-stream') &&
					response.body
				) {
					server.timeout(request, 0);
					// Ends normally if the adapter breaks it off at the end of its shutdown drain.
					return new Response(endQuietly(response.body), {
						status: response.status,
						statusText: response.statusText,
						headers: response.headers
					});
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
