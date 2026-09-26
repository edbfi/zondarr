<script lang="ts">
/**
 * Invitation filters component.
 *
 * Provides filtering and sorting controls for the invitation list:
 * - Enabled filter (all/enabled/disabled)
 * - Expired filter (all/active/expired)
 * - Sort by select (created_at, expires_at, use_count)
 * - Sort order toggle (asc/desc)
 *
 * Syncs filter state with URL search params for shareable URLs.
 *
 * @module $lib/components/invitations/invitation-filters
 */

import { ArrowDownAZ, ArrowUpAZ, Filter } from '@lucide/svelte';
import type { ListInvitationsParams } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import * as Select from '$lib/components/ui/select';

interface Props {
	enabled?: boolean;
	expired?: boolean;
	sortBy: 'created_at' | 'expires_at' | 'use_count';
	sortOrder: 'asc' | 'desc';
	onFilterChange: (params: Partial<ListInvitationsParams>) => void;
}

const { enabled, expired, sortBy, sortOrder, onFilterChange }: Props = $props();

// Convert boolean to select value
const enabledValue = $derived.by(() => {
	if (enabled === undefined) return 'all';
	return enabled ? 'enabled' : 'disabled';
});

const expiredValue = $derived.by(() => {
	if (expired === undefined) return 'all';
	return expired ? 'expired' : 'active';
});

/**
 * Handle enabled filter change.
 */
function handleEnabledChange(value: string | undefined) {
	if (value === 'all' || value === undefined) {
		onFilterChange({ enabled: undefined });
	} else {
		onFilterChange({ enabled: value === 'enabled' });
	}
}

/**
 * Handle expired filter change.
 */
function handleExpiredChange(value: string | undefined) {
	if (value === 'all' || value === undefined) {
		onFilterChange({ expired: undefined });
	} else {
		onFilterChange({ expired: value === 'expired' });
	}
}

/**
 * Handle sort by change.
 */
function handleSortByChange(value: string | undefined) {
	if (value) {
		onFilterChange({ sort_by: value as ListInvitationsParams['sort_by'] });
	}
}

/**
 * Toggle sort order.
 */
function toggleSortOrder() {
	onFilterChange({ sort_order: sortOrder === 'asc' ? 'desc' : 'asc' });
}

// Sort by options
const sortByOptions = [
	{ value: 'created_at', label: 'Created Date' },
	{ value: 'expires_at', label: 'Expiration Date' },
	{ value: 'use_count', label: 'Use Count' }
] as const;
</script>

<div
	class="flex flex-wrap items-center gap-3 rounded-lg border border-cr-border bg-cr-surface p-3"
	data-invitation-filters
>
	<div class="flex items-center gap-2 text-cr-text-muted">
		<Filter class="size-4" />
		<span class="text-sm font-medium">Filters</span>
	</div>

	<!-- Enabled filter -->
	<Select.Root type="single" value={enabledValue} onValueChange={handleEnabledChange}>
		<Select.Trigger
			class="w-32 border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border/50"
			aria-label="Filter by enabled status"
		>
			{enabledValue === 'all' ? 'All Status' : enabledValue === 'enabled' ? 'Enabled' : 'Disabled'}
		</Select.Trigger>
		<Select.Content class="border-cr-border bg-cr-surface">
			<Select.Item value="all" class="text-cr-text hover:bg-cr-border">All Status</Select.Item>
			<Select.Item value="enabled" class="text-cr-text hover:bg-cr-border">Enabled</Select.Item>
			<Select.Item value="disabled" class="text-cr-text hover:bg-cr-border">Disabled</Select.Item>
		</Select.Content>
	</Select.Root>

	<!-- Expired filter -->
	<Select.Root type="single" value={expiredValue} onValueChange={handleExpiredChange}>
		<Select.Trigger
			class="w-32 border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border/50"
			aria-label="Filter by expiration status"
		>
			{expiredValue === 'all' ? 'All' : expiredValue === 'active' ? 'Active' : 'Expired'}
		</Select.Trigger>
		<Select.Content class="border-cr-border bg-cr-surface">
			<Select.Item value="all" class="text-cr-text hover:bg-cr-border">All</Select.Item>
			<Select.Item value="active" class="text-cr-text hover:bg-cr-border">Active</Select.Item>
			<Select.Item value="expired" class="text-cr-text hover:bg-cr-border">Expired</Select.Item>
		</Select.Content>
	</Select.Root>

	<div class="h-6 w-px bg-cr-border hidden sm:block" aria-hidden="true"></div>

	<!-- Sort by -->
	<Select.Root type="single" value={sortBy} onValueChange={handleSortByChange}>
		<Select.Trigger
			class="w-40 border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border/50"
			aria-label="Sort by"
		>
			{sortByOptions.find((o) => o.value === sortBy)?.label ?? 'Sort by'}
		</Select.Trigger>
		<Select.Content class="border-cr-border bg-cr-surface">
			{#each sortByOptions as option}
				<Select.Item value={option.value} class="text-cr-text hover:bg-cr-border">
					{option.label}
				</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>

	<!-- Sort order toggle -->
	<Button
		variant="outline"
		size="icon"
		onclick={toggleSortOrder}
		aria-label={sortOrder === 'asc' ? 'Sort ascending' : 'Sort descending'}
		class="border-cr-border bg-cr-bg text-cr-text-muted hover:text-cr-accent hover:bg-cr-border/50"
	>
		{#if sortOrder === 'asc'}
			<ArrowUpAZ class="size-4" />
		{:else}
			<ArrowDownAZ class="size-4" />
		{/if}
	</Button>
</div>
