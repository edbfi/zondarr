<script lang="ts">
/**
 * Single log entry row — redesigned for at-a-glance readability.
 *
 * Fixed 36px height for virtual scrolling compatibility.
 * Level icon + relative timestamp + severity badge + source + message + field chips.
 * Clicking selects the row (detail panel handled by parent).
 * All content rendered as text nodes — no innerHTML.
 */

import { AlertTriangle, Bug, Info, ShieldAlert, XCircle } from '@lucide/svelte';
import type { LogEntry, LogLevel } from '$lib/stores/log-stream.svelte';

interface Props {
	entry: LogEntry;
	selected?: boolean;
	onSelect?: (seq: number) => void;
}

const { entry, selected = false, onSelect }: Props = $props();

// --- Level config ---

const LEVEL_CONFIG: Record<
	LogLevel,
	{
		icon: typeof Bug;
		badge: string;
		row: string;
		border: string;
	}
> = {
	DEBUG: {
		icon: Bug,
		badge: 'bg-muted text-muted-foreground',
		row: '',
		border: 'border-l-transparent'
	},
	INFO: {
		icon: Info,
		badge: 'bg-blue-500/15 text-blue-700 dark:text-blue-400',
		row: '',
		border: 'border-l-blue-500/50'
	},
	WARNING: {
		icon: AlertTriangle,
		badge: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
		row: '',
		border: 'border-l-amber-500'
	},
	ERROR: {
		icon: XCircle,
		badge: 'bg-red-500/15 text-red-700 dark:text-red-400',
		row: 'bg-red-500/5 dark:bg-red-500/8',
		border: 'border-l-red-500'
	},
	CRITICAL: {
		icon: ShieldAlert,
		badge: 'bg-red-600/20 text-red-700 dark:text-red-400',
		row: 'bg-red-500/10 dark:bg-red-500/15',
		border: 'border-l-red-600'
	}
};

const HIDDEN_FIELDS = new Set(['event', 'level', 'timestamp', 'logger_name', 'logger', 'message']);

const MAX_CHIPS = 3;

const config = $derived(LEVEL_CONFIG[entry.level]);

const LevelIcon = $derived(config.icon);

const iconColor = $derived.by(() => {
	const textClasses = config.badge.split(' ').filter((c) => c.startsWith('text-'));
	return textClasses.join(' ') || 'text-muted-foreground';
});

// --- Relative timestamp ---

const absoluteTime = $derived.by(() => {
	if (!entry.timestamp) return '';
	try {
		const d = new Date(entry.timestamp);
		return d.toLocaleTimeString('en-GB', {
			hour12: false,
			fractionalSecondDigits: 3
		});
	} catch {
		return entry.timestamp;
	}
});

const relativeTime = $derived.by(() => {
	if (!entry.timestamp) return '';
	try {
		const d = new Date(entry.timestamp);
		const diff = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	} catch {
		return '';
	}
});

// --- Truncated logger name ---

const shortLogger = $derived.by(() => {
	const parts = entry.logger_name.split('.');
	if (parts.length <= 2) return entry.logger_name;
	return parts.slice(-2).join('.');
});

// --- Inline field chips (up to 3, skip already-displayed fields) ---

const fieldChips = $derived.by(() => {
	const chips: Array<{ key: string; value: string }> = [];
	for (const [key, value] of Object.entries(entry.fields)) {
		if (HIDDEN_FIELDS.has(key)) continue;
		chips.push({ key, value: String(value) });
		if (chips.length >= MAX_CHIPS) break;
	}
	return chips;
});

function handleClick() {
	onSelect?.(entry.seq);
}
</script>

<button
	type="button"
	aria-pressed={selected}
	class="flex w-full text-left h-9 items-center gap-1.5 border-l-2 px-2 font-mono text-xs transition-colors
		{config.border} {config.row}
		{selected ? 'bg-accent/50 dark:bg-accent/30' : 'hover:bg-muted/50'}
		cursor-pointer"
	onclick={handleClick}
>
	<!-- Level icon -->
	<LevelIcon class="size-3.5 shrink-0 {iconColor}" />

	<!-- Relative timestamp -->
	<span class="w-12 shrink-0 text-right text-muted-foreground tabular-nums" title={absoluteTime}>
		{relativeTime}
	</span>

	<!-- Level badge -->
	<span
		class="inline-flex w-16 shrink-0 items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none {config.badge}"
	>
		{entry.level}
	</span>

	<!-- Logger source (truncated) -->
	<span class="w-24 shrink-0 truncate text-muted-foreground" title={entry.logger_name}>
		{shortLogger}
	</span>

	<!-- Message -->
	<span class="min-w-0 flex-1 truncate" title={entry.message}>
		{entry.message}
	</span>

	<!-- Inline field chips -->
	{#if fieldChips.length > 0}
		<span class="hidden items-center gap-1 md:flex shrink-0">
			{#each fieldChips as chip (chip.key)}
				<span
					class="inline-flex max-w-32 items-center truncate rounded bg-muted/80 px-1.5 py-0.5 text-[10px] text-muted-foreground"
					title="{chip.key}={chip.value}"
				>
					{chip.key}={chip.value}
				</span>
			{/each}
		</span>
	{/if}
</button>
