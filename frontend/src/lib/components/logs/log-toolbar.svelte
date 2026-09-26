<script lang="ts">
/**
 * Log viewer toolbar with filter controls.
 *
 * Provides level dropdown with colored indicators, source dropdown,
 * debounced search with Cmd+F shortcut, quick-filter badges for
 * error/warning counts, clear filters button, and entry count.
 */

import { AlertTriangle, Eraser, FilterX, Pause, Play, Search, XCircle } from '@lucide/svelte';
import { Badge } from '$lib/components/ui/badge';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import * as Select from '$lib/components/ui/select';
import { Separator } from '$lib/components/ui/separator';

interface Props {
	levelFilter: string;
	sourceFilter: string;
	searchQuery: string;
	entryCount: number;
	totalCount: number;
	errorCount: number;
	warningCount: number;
	sources: string[];
	connected: boolean;
	loading: boolean;
	paused: boolean;
	error: string | null;
	onLevelChange: (value: string) => void;
	onSourceChange: (value: string) => void;
	onSearchChange: (value: string) => void;
	onClear: () => void;
	onTogglePause: () => void;
	onClearFilters: () => void;
}

const {
	levelFilter,
	sourceFilter,
	searchQuery,
	entryCount,
	totalCount,
	errorCount,
	warningCount,
	sources,
	connected,
	loading,
	paused,
	error,
	onLevelChange,
	onSourceChange,
	onSearchChange,
	onClear,
	onTogglePause,
	onClearFilters
}: Props = $props();

// Level options with color classes for the dot indicators
const levelOptions: Array<{
	value: string;
	label: string;
	dot: string;
}> = [
	{ value: 'ALL', label: 'All Levels', dot: 'bg-muted-foreground' },
	{ value: 'DEBUG', label: 'Debug', dot: 'bg-muted-foreground' },
	{ value: 'INFO', label: 'Info', dot: 'bg-blue-500' },
	{ value: 'WARNING', label: 'Warning', dot: 'bg-amber-500' },
	{ value: 'ERROR', label: 'Error', dot: 'bg-red-500' },
	{ value: 'CRITICAL', label: 'Critical', dot: 'bg-red-600' }
];

const defaultLevel = { value: 'ALL', label: 'All Levels', dot: 'bg-muted-foreground' } as const;

const selectedLevel = $derived(levelOptions.find((o) => o.value === levelFilter) ?? defaultLevel);

const selectedSourceLabel = $derived(sourceFilter === '' ? 'All Sources' : sourceFilter);

const hasActiveFilters = $derived(
	levelFilter !== 'ALL' || sourceFilter !== '' || searchQuery !== ''
);

// Debounced search
let searchInput: HTMLInputElement | null = $state(null);
let internalSearch = $state('');
let debounceTimer: ReturnType<typeof setTimeout> | undefined;

function handleSearchInput(value: string) {
	internalSearch = value;
	clearTimeout(debounceTimer);
	debounceTimer = setTimeout(() => {
		onSearchChange(value);
	}, 300);
}

// Cmd/Ctrl+F keyboard shortcut
function handleKeydown(e: KeyboardEvent) {
	if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
		e.preventDefault();
		searchInput?.focus();
	}
}

$effect(() => {
	document.addEventListener('keydown', handleKeydown);
	return () => document.removeEventListener('keydown', handleKeydown);
});

// Clear debounce timer on teardown
$effect(() => {
	return () => clearTimeout(debounceTimer);
});

// Sync internal search with external prop (e.g., when cleared externally)
$effect(() => {
	if (searchQuery !== internalSearch) {
		internalSearch = searchQuery;
	}
});
</script>

<div class="flex flex-wrap items-center gap-2">
	<!-- Connection status + Pause -->
	<div class="flex items-center gap-1.5">
		<div
			class="flex items-center gap-1.5"
			title={error ?? (connected ? 'Connected' : loading ? 'Connecting...' : 'Disconnected')}
		>
			{#if loading}
				<span class="inline-block size-2 animate-pulse rounded-full bg-amber-500"></span>
				<span class="text-xs text-muted-foreground">Connecting</span>
			{:else}
				<span
					class="inline-block size-2 rounded-full {connected ? 'bg-green-500' : 'bg-red-500'}"
				></span>
				<span class="text-xs text-muted-foreground">
					{connected ? 'Live' : 'Disconnected'}
				</span>
			{/if}
		</div>

		<Button
			variant={paused ? 'default' : 'outline'}
			size="icon-sm"
			onclick={onTogglePause}
			title={paused ? 'Resume' : 'Pause'}
		>
			{#if paused}
				<Play class="size-3.5" />
			{:else}
				<Pause class="size-3.5" />
			{/if}
		</Button>
	</div>

	<Separator orientation="vertical" class="!h-5" />

	<!-- Level filter with colored dots -->
	<Select.Root
		type="single"
		value={levelFilter}
		onValueChange={(v) => {
	if (v) onLevelChange(v);
}}
	>
		<Select.Trigger size="sm" class="w-36">
			<span class="flex items-center gap-2">
				<span class="inline-block size-2 rounded-full {selectedLevel.dot}"></span>
				{selectedLevel.label}
			</span>
		</Select.Trigger>
		<Select.Content>
			{#each levelOptions as opt (opt.value)}
				<Select.Item value={opt.value}>
					{#snippet children({
	selected: _s,
	highlighted: _h
})}
						<span class="absolute end-2 flex size-3.5 items-center justify-center">
							{#if _s}
								<svg
									class="size-4"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
									aria-hidden="true"
								>
									<polyline points="20 6 9 17 4 12" />
								</svg>
							{/if}
						</span>
						<span class="flex items-center gap-2">
							<span class="inline-block size-2 rounded-full {opt.dot}"></span>
							{opt.label}
						</span>
					{/snippet}
				</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>

	<!-- Quick-filter badges for errors and warnings -->
	{#if errorCount > 0}
		<button
			type="button"
			class="inline-flex items-center gap-1 rounded-full border border-transparent bg-red-500/15 px-2 py-0.5 text-xs font-medium text-red-700 transition-colors hover:bg-red-500/25 dark:text-red-400 {levelFilter === 'ERROR' ? 'ring-1 ring-red-500/50' : ''}"
			onclick={() => onLevelChange(levelFilter === 'ERROR' ? 'ALL' : 'ERROR')}
			title="Toggle error filter"
		>
			<XCircle class="size-3" />
			{errorCount}
		</button>
	{/if}
	{#if warningCount > 0}
		<button
			type="button"
			class="inline-flex items-center gap-1 rounded-full border border-transparent bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-700 transition-colors hover:bg-amber-500/25 dark:text-amber-400 {levelFilter === 'WARNING' ? 'ring-1 ring-amber-500/50' : ''}"
			onclick={() => onLevelChange(levelFilter === 'WARNING' ? 'ALL' : 'WARNING')}
			title="Toggle warning filter"
		>
			<AlertTriangle class="size-3" />
			{warningCount}
		</button>
	{/if}

	<Separator orientation="vertical" class="!h-5" />

	<!-- Source filter dropdown -->
	<Select.Root
		type="single"
		value={sourceFilter || 'ALL_SOURCES'}
		onValueChange={(v) => {
	if (v === 'ALL_SOURCES') {
		onSourceChange('');
	} else if (v) {
		onSourceChange(v);
	}
}}
	>
		<Select.Trigger size="sm" class="w-40">
			<span class="truncate">{selectedSourceLabel}</span>
		</Select.Trigger>
		<Select.Content>
			<Select.Item value="ALL_SOURCES">All Sources</Select.Item>
			{#each sources as source (source)}
				<Select.Item value={source}>{source}</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>

	<Separator orientation="vertical" class="!h-5" />

	<!-- Search with debounce and result count -->
	<div class="relative flex items-center gap-1.5">
		<Search class="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
		<Input
			bind:ref={searchInput}
			placeholder="Search... (Ctrl+F)"
			value={internalSearch}
			oninput={(e) => handleSearchInput(e.currentTarget.value)}
			class="h-8 w-48 pl-7 text-xs"
		/>
		{#if internalSearch}
			<span class="text-xs text-muted-foreground whitespace-nowrap"> {entryCount} results </span>
		{/if}
	</div>

	<!-- Clear log entries -->
	<Button variant="outline" size="sm" onclick={onClear} class="h-8 gap-1 text-xs">
		<Eraser class="size-3.5" />
		Clear
	</Button>

	<!-- Clear filters (only visible when filters are active) -->
	{#if hasActiveFilters}
		<Button variant="outline" size="sm" onclick={onClearFilters} class="h-8 gap-1 text-xs">
			<FilterX class="size-3.5" />
			Clear Filters
		</Button>
	{/if}

	<!-- Entry count -->
	<Badge variant="secondary" class="ml-auto text-xs">
		{#if hasActiveFilters}
			{entryCount.toLocaleString()}
			/ {totalCount.toLocaleString()}
		{:else}
			{entryCount.toLocaleString()}
			entries
		{/if}
	</Badge>
</div>
