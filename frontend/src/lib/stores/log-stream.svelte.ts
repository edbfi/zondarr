/**
 * SSE-based log stream store.
 *
 * Connects to the backend's `/api/v1/logs/stream` SSE endpoint and maintains
 * a client-side ring buffer of log entries for the log viewer UI.
 *
 * @module $lib/stores/log-stream
 */

import * as env from '$app/env/public';

// =============================================================================
// Types
// =============================================================================

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface LogEntry {
	seq: number;
	timestamp: string;
	level: LogLevel;
	logger_name: string;
	message: string;
	fields: Record<string, string>;
}

export const LEVEL_ORDER: Record<LogLevel, number> = {
	DEBUG: 10,
	INFO: 20,
	WARNING: 30,
	ERROR: 40,
	CRITICAL: 50
};

// =============================================================================
// State
// =============================================================================

const MAX_ENTRIES = 2000;

let _entries = $state.raw<LogEntry[]>([]);
let _connected = $state(false);
let _loading = $state(false);
let _error = $state<string | null>(null);
let _lastSeq = 0;

let _eventSource: EventSource | null = null;
let _pending: LogEntry[] = [];
let _rafId: number | null = null;
let _flushTimer: ReturnType<typeof setInterval> | null = null;

// =============================================================================
// Internal helpers
// =============================================================================

function flushPending(): void {
	if (_rafId !== null) {
		cancelAnimationFrame(_rafId);
		_rafId = null;
	}
	if (_pending.length === 0) return;

	const batch = _pending;
	_pending = [];

	const combined = _entries.concat(batch);
	if (combined.length >= MAX_ENTRIES) {
		_entries = combined.slice(-(MAX_ENTRIES - 100));
	} else {
		_entries = combined;
	}
}

// =============================================================================
// API
// =============================================================================

/**
 * Connect to the SSE log stream.
 */
export function connect(): void {
	if (_eventSource) return;

	_loading = true;

	const API_BASE_URL = env.PUBLIC_API_URL ?? '';
	const url = `${API_BASE_URL}/api/v1/logs/stream`;

	const es = new EventSource(url, { withCredentials: true });
	_eventSource = es;

	es.onopen = () => {
		_connected = true;
		_loading = false;
		_error = null;
		// Don't reset _lastSeq here — on auto-reconnect, keeping _lastSeq
		// allows the existing dedup check to reject already-seen backfill entries.
		// _lastSeq is reset in disconnect() for genuinely fresh connections.
	};

	// Fallback flush for when RAF is paused (backgrounded tab)
	_flushTimer = setInterval(flushPending, 2000);

	es.addEventListener('log', (event: MessageEvent<string>) => {
		try {
			const entry = JSON.parse(event.data) as LogEntry;

			// Detect seq regression: if the backend restarts, its seq counter
			// resets to 0 while _lastSeq stays high. A large backward jump
			// (>50%) indicates a restart rather than normal backfill overlap.
			if (_lastSeq > 0 && entry.seq < _lastSeq && entry.seq < _lastSeq / 2) {
				_lastSeq = 0;
				_entries = [];
				_pending = [];
			}

			// Deduplicate by seq on reconnect
			if (entry.seq <= _lastSeq) return;
			_lastSeq = entry.seq;

			_pending.push(entry);
			// Cap pending buffer to prevent unbounded growth when tab is backgrounded
			if (_pending.length > MAX_ENTRIES) {
				_pending = _pending.slice(-MAX_ENTRIES);
			}
			if (_rafId === null) {
				_rafId = requestAnimationFrame(flushPending);
			}
		} catch {
			// Ignore malformed events
		}
	});

	es.onerror = () => {
		_connected = false;
		_loading = false;
		_error = 'Connection lost. Reconnecting...';
	};
}

/**
 * Disconnect from the SSE log stream.
 */
export function disconnect(): void {
	if (_flushTimer !== null) {
		clearInterval(_flushTimer);
		_flushTimer = null;
	}
	if (_rafId !== null) {
		cancelAnimationFrame(_rafId);
		_rafId = null;
	}
	_pending = [];
	if (_eventSource) {
		_eventSource.close();
		_eventSource = null;
	}
	_connected = false;
	_loading = false;
	_error = null;
	_lastSeq = 0;
}

/**
 * Clear all buffered log entries.
 */
export function clearEntries(): void {
	_entries = [];
}

// =============================================================================
// Exports (reactive getters)
// =============================================================================

export function getEntries(): LogEntry[] {
	return _entries;
}

export function getConnected(): boolean {
	return _connected;
}

export function getLoading(): boolean {
	return _loading;
}

export function getError(): string | null {
	return _error;
}
