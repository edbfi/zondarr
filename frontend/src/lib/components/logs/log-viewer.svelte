<script lang="ts">
/**
 * Main log viewer container.
 *
 * Manages SSE lifecycle, filtering, pause/resume, and auto-scroll behavior.
 * Connects on mount, disconnects on cleanup.
 */

import { ArrowDown, ScrollText } from '@lucide/svelte';
import EmptyState from '$lib/components/empty-state.svelte';
import { Button } from '$lib/components/ui/button';
import { Skeleton } from '$lib/components/ui/skeleton';
import {
	clearEntries,
	connect,
	disconnect,
	getConnected,
	getEntries,
	getError,
	getLoading,
	LEVEL_ORDER,
	type LogEntry,
	type LogLevel
} from '$lib/stores/log-stream.svelte';
import LogDetailPanel from './log-detail-panel.svelte';
import LogEntryRow from './log-entry.svelte';
import LogToolbar from './log-toolbar.svelte';

interface Props {
	selectedId?: number | null;
	onSelectionChange?: (entry: LogEntry | null) => void;
}

let { selectedId = $bindable(null), onSelectionChange }: Props = $props();

// Filter state
let levelFilter = $state('ALL');
let sourceFilter = $state('');
let searchQuery = $state('');

// Pause state
let paused = $state(false);
let pausedEntries = $state.raw<LogEntry[]>([]);

// Auto-scroll state
let autoScroll = $state(true);
let scrollContainer: HTMLDivElement | undefined = $state();

// Virtual scrolling constants and state
const ROW_HEIGHT = 36; // h-9 = 36px
const OVERSCAN = 10;
let containerHeight = $state(0);
let currentScrollTop = $state(0);
let rafPending = $state(false);

// Reactive getters
const entries = $derived(getEntries());
const connected = $derived(getConnected());
const loading = $derived(getLoading());
const error = $derived(getError());

// Snapshot entries when paused
const displayEntries = $derived(paused ? pausedEntries : entries);

// Filtered entries
const filteredEntries = $derived.by(() => {
	let result = displayEntries;

	if (levelFilter !== 'ALL') {
		const minLevel = LEVEL_ORDER[levelFilter as LogLevel] ?? 0;
		result = result.filter((e) => (LEVEL_ORDER[e.level] ?? 0) >= minLevel);
	}

	if (sourceFilter) {
		const src = sourceFilter.toLowerCase();
		result = result.filter((e) => e.logger_name.toLowerCase().includes(src));
	}

	if (searchQuery) {
		const q = searchQuery.toLowerCase();
		result = result.filter(
			(e) =>
				e.message.toLowerCase().includes(q) ||
				e.logger_name.toLowerCase().includes(q) ||
				Object.values(e.fields).some((v) => v.toLowerCase().includes(q))
		);
	}

	return result;
});

const totalCount = $derived(displayEntries.length);

// Virtual scrolling calculations
const totalHeight = $derived(filteredEntries.length * ROW_HEIGHT);
const startIndex = $derived(Math.max(0, Math.floor(currentScrollTop / ROW_HEIGHT) - OVERSCAN));
const visibleCount = $derived(Math.ceil(containerHeight / ROW_HEIGHT) + OVERSCAN * 2);
const endIndex = $derived(Math.min(startIndex + visibleCount, filteredEntries.length));
const visibleEntries = $derived(filteredEntries.slice(startIndex, endIndex));
const topSpacerHeight = $derived(startIndex * ROW_HEIGHT);
const bottomSpacerHeight = $derived(Math.max(0, (filteredEntries.length - endIndex) * ROW_HEIGHT));

// Counts for toolbar quick-filter badges
const errorCount = $derived(displayEntries.filter((e) => e.level === 'ERROR').length);
const warningCount = $derived(displayEntries.filter((e) => e.level === 'WARNING').length);

// Unique source logger names for the source dropdown
const sources = $derived.by(() => {
	const seen = new Set<string>();
	for (const e of displayEntries) {
		seen.add(e.logger_name);
	}
	return [...seen].sort();
});

function clearFilters() {
	levelFilter = 'ALL';
	sourceFilter = '';
	searchQuery = '';
}

// Selected entry for detail panel
const selectedEntry = $derived.by(() => {
	if (selectedId == null) return null;
	return filteredEntries.find((e) => e.seq === selectedId) ?? null;
});

const panelOpen = $derived(selectedEntry != null);

// Auto-scroll when new entries arrive
$effect(() => {
	// Track dependency on filtered entries length and total height
	filteredEntries.length;
	totalHeight;

	if (autoScroll && scrollContainer) {
		requestAnimationFrame(() => {
			if (scrollContainer) {
				scrollContainer.scrollTop = scrollContainer.scrollHeight;
			}
		});
	}
});

// Connect on mount, disconnect on cleanup
$effect(() => {
	connect();
	return () => disconnect();
});

// Measure container height for virtual scrolling
$effect(() => {
	if (!scrollContainer) return;
	const el = scrollContainer;
	containerHeight = el.clientHeight;
	const observer = new ResizeObserver((resizeEntries) => {
		for (const resizeEntry of resizeEntries) {
			containerHeight = resizeEntry.contentRect.height;
		}
	});
	observer.observe(el);
	return () => observer.disconnect();
});

function handleScroll() {
	if (!scrollContainer) return;
	const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
	autoScroll = scrollHeight - scrollTop - clientHeight < 50;

	if (!rafPending) {
		rafPending = true;
		requestAnimationFrame(() => {
			if (scrollContainer) {
				currentScrollTop = scrollContainer.scrollTop;
			}
			rafPending = false;
		});
	}
}

function jumpToLatest() {
	if (scrollContainer) {
		scrollContainer.scrollTop = scrollContainer.scrollHeight;
		autoScroll = true;
	}
}

function togglePause() {
	if (paused) {
		paused = false;
	} else {
		pausedEntries = entries;
		paused = true;
	}
}

function scrollIndexIntoView(index: number) {
	if (!scrollContainer) return;
	const itemTop = index * ROW_HEIGHT;
	const itemBottom = itemTop + ROW_HEIGHT;
	const viewTop = scrollContainer.scrollTop;
	const viewBottom = viewTop + scrollContainer.clientHeight;

	if (itemTop < viewTop) {
		scrollContainer.scrollTop = itemTop;
	} else if (itemBottom > viewBottom) {
		scrollContainer.scrollTop = itemBottom - scrollContainer.clientHeight;
	}
}

function handleKeydown(e: KeyboardEvent) {
	if (selectedId == null) return;
	if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;

	const target = e.target as HTMLElement;
	if (
		target.tagName === 'INPUT' ||
		target.tagName === 'TEXTAREA' ||
		target.tagName === 'SELECT' ||
		target.isContentEditable
	) {
		return;
	}

	const currentIndex = filteredEntries.findIndex((entry) => entry.seq === selectedId);
	if (currentIndex === -1) return;

	const nextIndex = e.key === 'ArrowDown' ? currentIndex + 1 : currentIndex - 1;
	const nextEntry = filteredEntries[nextIndex];
	if (!nextEntry) return;

	e.preventDefault();
	selectedId = nextEntry.seq;
	onSelectionChange?.(nextEntry);
	scrollIndexIntoView(nextIndex);
}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex flex-col gap-3">
	<LogToolbar
		{levelFilter}
		{sourceFilter}
		{searchQuery}
		entryCount={filteredEntries.length}
		{totalCount}
		{errorCount}
		{warningCount}
		{sources}
		{connected}
		{loading}
		{paused}
		{error}
		onLevelChange={(v) => (levelFilter = v)}
		onSourceChange={(v) => (sourceFilter = v)}
		onSearchChange={(v) => (searchQuery = v)}
		onClear={clearEntries}
		onTogglePause={togglePause}
		onClearFilters={clearFilters}
	/>

	<!-- Split layout: log list + detail panel -->
	<div class="flex h-[calc(100vh-13rem)] gap-0">
		<!-- Log list -->
		<div class="relative min-w-0 flex-1">
			<div
				bind:this={scrollContainer}
				onscroll={handleScroll}
				class="h-full overflow-y-auto rounded-md border border-cr-border bg-cr-bg-card"
				class:rounded-r-none={panelOpen}
				class:border-r-0={panelOpen}
			>
				{#if loading}
					<div class="space-y-1 p-2">
						{#each Array(8) as _}
							<Skeleton class="h-9 w-full" />
						{/each}
					</div>
				{:else if filteredEntries.length === 0}
					{#if displayEntries.length === 0}
						<EmptyState
							title="No log entries yet"
							description="Log entries will appear here as they are generated by the backend."
							class="h-full border-none"
						>
							{#snippet icon()}
								<ScrollText class="size-8" />
							{/snippet}
						</EmptyState>
					{:else}
						<EmptyState
							title="No matching entries"
							description="Try adjusting your filters or search query."
							class="h-full border-none"
						>
							{#snippet icon()}
								<ScrollText class="size-8" />
							{/snippet}
						</EmptyState>
					{/if}
				{:else}
					<div style="height:{topSpacerHeight}px" aria-hidden="true"></div>
					{#each visibleEntries as entry (entry.seq)}
						<LogEntryRow
							{entry}
							selected={selectedId === entry.seq}
							onSelect={(seq) => {
	const isDeselect = selectedId === seq;
	selectedId = isDeselect ? null : seq;
	onSelectionChange?.(isDeselect ? null : entry);
}}
						/>
					{/each}
					<div style="height:{bottomSpacerHeight}px" aria-hidden="true"></div>
				{/if}
			</div>

			<!-- Jump to latest button -->
			{#if !autoScroll && !paused}
				<div class="absolute bottom-3 left-1/2 -translate-x-1/2">
					<Button variant="secondary" size="sm" onclick={jumpToLatest} class="gap-1.5 shadow-md">
						<ArrowDown class="size-3.5" />
						Jump to latest
					</Button>
				</div>
			{/if}
		</div>

		<!-- Detail panel -->
		{#if panelOpen}
			<div
				class="h-full w-[38%] shrink-0 overflow-hidden rounded-r-md border border-l-0 border-cr-border"
			>
				<LogDetailPanel
					entry={selectedEntry}
					onclose={() => {
	selectedId = null;
	onSelectionChange?.(null);
}}
				/>
			</div>
		{/if}
	</div>
</div>
