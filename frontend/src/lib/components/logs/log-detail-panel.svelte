<script lang="ts">
/**
 * Log detail side panel.
 *
 * Shows structured details for the selected log entry.
 * Renders in the right portion of a split layout when a log entry is selected.
 */

import { AlertTriangle, Bug, Copy, Info, ShieldAlert, X, XCircle } from '@lucide/svelte';
import { fly } from 'svelte/transition';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import { Separator } from '$lib/components/ui/separator';
import type { LogEntry } from '$lib/stores/log-stream.svelte';

interface Props {
	entry: LogEntry | null;
	onclose: () => void;
}

const { entry, onclose }: Props = $props();

const STANDARD_KEYS = new Set(['event', 'level', 'timestamp', 'logger_name']);

interface LevelStyle {
	color: string;
	badgeClass: string;
	icon: typeof Info;
}

const DEFAULT_LEVEL: LevelStyle = {
	color: 'text-blue-500 dark:text-blue-400',
	badgeClass: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30',
	icon: Info
};

const levelConfig: Record<string, LevelStyle> = {
	DEBUG: {
		color: 'text-muted-foreground',
		badgeClass: 'bg-muted text-muted-foreground border-muted',
		icon: Bug
	},
	INFO: {
		color: 'text-blue-500 dark:text-blue-400',
		badgeClass: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30',
		icon: Info
	},
	WARNING: {
		color: 'text-amber-500 dark:text-amber-400',
		badgeClass: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30',
		icon: AlertTriangle
	},
	ERROR: {
		color: 'text-red-500 dark:text-red-400',
		badgeClass: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/30',
		icon: XCircle
	},
	CRITICAL: {
		color: 'text-red-600 dark:text-red-400',
		badgeClass: 'bg-red-600/15 text-red-700 dark:text-red-400 border-red-600/30',
		icon: ShieldAlert
	}
};

const config = $derived(levelConfig[entry?.level ?? ''] ?? DEFAULT_LEVEL);

const LevelIcon = $derived(config.icon);

const formattedTimestamp = $derived.by(() => {
	if (!entry?.timestamp) return '';
	try {
		const d = new Date(entry.timestamp);
		return d.toLocaleString('en-GB', {
			hour12: false,
			fractionalSecondDigits: 3
		});
	} catch {
		return entry.timestamp;
	}
});

const relativeTime = $derived.by(() => {
	if (!entry?.timestamp) return '';
	try {
		const d = new Date(entry.timestamp);
		const diff = Math.max(0, Date.now() - d.getTime());
		const seconds = Math.floor(diff / 1000);
		if (seconds < 60) return `${seconds}s ago`;
		const minutes = Math.floor(seconds / 60);
		if (minutes < 60) return `${minutes}m ago`;
		const hours = Math.floor(minutes / 60);
		if (hours < 24) return `${hours}h ago`;
		return `${Math.floor(hours / 24)}d ago`;
	} catch {
		return '';
	}
});

const extraFields = $derived.by(() => {
	if (!entry) return [];
	return Object.entries(entry.fields).filter(([key]) => !STANDARD_KEYS.has(key));
});

function isJsonLike(value: string): boolean {
	const trimmed = value.trim();
	return (
		(trimmed.startsWith('{') && trimmed.endsWith('}')) ||
		(trimmed.startsWith('[') && trimmed.endsWith(']'))
	);
}

function formatJsonValue(value: string): string {
	try {
		return JSON.stringify(JSON.parse(value), null, 2);
	} catch {
		return value;
	}
}

let copied = $state(false);

async function copyAsJson() {
	if (!entry) return;
	const raw = JSON.stringify(entry, null, 2);
	try {
		await navigator.clipboard.writeText(raw);
		copied = true;
		setTimeout(() => (copied = false), 2000);
	} catch {
		// Clipboard API can fail in non-secure contexts or when permissions are denied
	}
}

function handleKeydown(e: KeyboardEvent) {
	if (e.key === 'Escape') {
		onclose();
	}
}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if entry}
	<div
		class="flex h-full flex-col border-l border-cr-border bg-cr-bg-card"
		transition:fly={{ x: 100, duration: 200 }}
	>
		<!-- Header -->
		<div class="flex items-center gap-2 border-b border-cr-border px-3 py-2">
			<LevelIcon class="size-4 shrink-0 {config.color}" />
			<Badge variant="outline" class={config.badgeClass}>
				{entry.level}
			</Badge>
			<div class="min-w-0 flex-1">
				<span class="text-xs text-muted-foreground">
					{formattedTimestamp}
				</span>
				{#if relativeTime}
					<span class="text-xs text-muted-foreground/60"> ({relativeTime}) </span>
				{/if}
			</div>
			<Button variant="ghost" size="icon" class="size-7 shrink-0" onclick={onclose}>
				<X class="size-4" />
				<span class="sr-only">Close</span>
			</Button>
		</div>

		<!-- Body -->
		<div class="flex-1 overflow-y-auto p-3 text-sm">
			<!-- Message -->
			<div class="mb-3">
				<div class="mb-1 text-xs font-medium text-muted-foreground uppercase">Message</div>
				<div class="font-mono text-sm leading-relaxed break-words">
					{entry.message}
				</div>
			</div>

			<Separator class="my-3" />

			<!-- Source -->
			<div class="mb-3">
				<div class="mb-1 text-xs font-medium text-muted-foreground uppercase">Source</div>
				<div class="font-mono text-xs text-muted-foreground break-all">
					{entry.logger_name}
				</div>
			</div>

			<!-- Fields -->
			{#if extraFields.length > 0}
				<Separator class="my-3" />
				<div>
					<div class="mb-2 text-xs font-medium text-muted-foreground uppercase">Fields</div>
					<div class="space-y-2">
						{#each extraFields as [key, value] (key)}
							<div>
								<div class="text-xs font-semibold text-muted-foreground">
									{key}
								</div>
								{#if isJsonLike(value)}
									<pre
										class="mt-0.5 overflow-x-auto rounded bg-cr-surface/50 px-2 py-1 font-mono text-xs leading-relaxed break-words whitespace-pre-wrap"
									>{formatJsonValue(value)}</pre>
								{:else}
									<div class="mt-0.5 font-mono text-xs break-words">
										{value}
									</div>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="border-t border-cr-border px-3 py-2">
			<Button variant="outline" size="sm" class="w-full gap-1.5" onclick={copyAsJson}>
				<Copy class="size-3.5" />
				{copied ? 'Copied!' : 'Copy as JSON'}
			</Button>
		</div>
	</div>
{/if}
