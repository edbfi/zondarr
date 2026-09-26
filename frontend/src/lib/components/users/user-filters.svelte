<script lang="ts">
/**
 * User filters component.
 *
 * Provides filtering and sorting controls for the user list:
 * - Server filter (select from available servers)
 * - Invitation filter (select from available invitations)
 * - Enabled filter (all/enabled/disabled)
 * - Expired filter (all/active/expired)
 * - Sort by select (created_at, username, expires_at)
 * - Sort order toggle (asc/desc)
 *
 * Syncs filter state with URL search params for shareable URLs.
 *
 * @module $lib/components/users/user-filters
 */

import { ArrowDownAZ, ArrowUpAZ, Filter, Search, X } from '@lucide/svelte';
import type {
	InvitationResponse,
	ListUsersParams,
	MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import * as Select from '$lib/components/ui/select';
import { getProviderBadgeStyle } from '$lib/stores/providers.svelte';

interface Props {
	serverId?: string;
	invitationId?: string;
	enabled?: boolean;
	expired?: boolean;
	search?: string;
	sortBy: 'created_at' | 'username' | 'expires_at';
	sortOrder: 'asc' | 'desc';
	servers: MediaServerWithLibrariesResponse[];
	invitations: InvitationResponse[];
	onFilterChange: (params: Partial<ListUsersParams>) => void;
}

const {
	serverId,
	invitationId,
	enabled,
	expired,
	search,
	sortBy,
	sortOrder,
	servers,
	invitations,
	onFilterChange
}: Props = $props();

let searchValue = $state('');
let searchTimer: ReturnType<typeof setTimeout> | null = null;

$effect(() => {
	searchValue = search ?? '';
});

$effect(() => {
	return () => {
		if (searchTimer !== null) {
			clearTimeout(searchTimer);
		}
	};
});

// Convert boolean to select value
const enabledValue = $derived.by(() => {
	if (enabled === undefined) return 'all';
	return enabled ? 'enabled' : 'disabled';
});

const expiredValue = $derived.by(() => {
	if (expired === undefined) return 'all';
	return expired ? 'expired' : 'active';
});

// Get selected server name for display
const selectedServerName = $derived.by(() => {
	if (!serverId) return 'All Servers';
	const server = servers.find((s) => s.id === serverId);
	return server?.name ?? 'All Servers';
});

// Get selected invitation code for display
const selectedInvitationCode = $derived.by(() => {
	if (!invitationId) return 'All Invitations';
	const invitation = invitations.find((i) => i.id === invitationId);
	return invitation?.code ?? 'All Invitations';
});

/**
 * Handle server filter change.
 */
function handleServerChange(value: string | undefined) {
	if (value === 'all' || value === undefined) {
		onFilterChange({ server_id: undefined });
	} else {
		onFilterChange({ server_id: value });
	}
}

/**
 * Handle invitation filter change.
 */
function handleInvitationChange(value: string | undefined) {
	if (value === 'all' || value === undefined) {
		onFilterChange({ invitation_id: undefined });
	} else {
		onFilterChange({ invitation_id: value });
	}
}

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

function handleSearchInput(event: Event) {
	searchValue = (event.currentTarget as HTMLInputElement).value;
	if (searchTimer !== null) {
		clearTimeout(searchTimer);
	}
	searchTimer = setTimeout(() => {
		onFilterChange({ search: searchValue.trim() || undefined });
		searchTimer = null;
	}, 250);
}

function clearSearch() {
	searchValue = '';
	if (searchTimer !== null) {
		clearTimeout(searchTimer);
		searchTimer = null;
	}
	onFilterChange({ search: undefined });
}

/**
 * Handle sort by change.
 */
function handleSortByChange(value: string | undefined) {
	if (value) {
		onFilterChange({ sort_by: value as ListUsersParams['sort_by'] });
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
	{ value: 'username', label: 'Username' },
	{ value: 'expires_at', label: 'Expiration Date' }
] as const;
</script>

<div
	class="flex flex-wrap items-center gap-3 rounded-lg border border-cr-border bg-cr-surface p-3"
	data-user-filters
>
	<div class="flex items-center gap-2 text-cr-text-muted">
		<Filter class="size-4" />
		<span class="text-sm font-medium">Filters</span>
	</div>

	<div class="relative min-w-52 flex-1 sm:flex-none">
		<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-cr-text-muted" />
		<Input
			type="search"
			value={searchValue}
			oninput={handleSearchInput}
			placeholder="Search users"
			aria-label="Search users"
			class="h-9 border-cr-border bg-cr-bg pl-8 pr-8 text-cr-text placeholder:text-cr-text-muted/60"
			data-user-search
		/>
		{#if searchValue}
			<button
				type="button"
				onclick={clearSearch}
				aria-label="Clear search"
				class="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-cr-text-muted hover:text-cr-text"
			>
				<X class="size-3.5" />
			</button>
		{/if}
	</div>

	<!-- Server filter -->
	<Select.Root type="single" value={serverId ?? 'all'} onValueChange={handleServerChange}>
		<Select.Trigger
			class="w-36 border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border/50"
			aria-label="Filter by server"
		>
			<span class="truncate">{selectedServerName}</span>
		</Select.Trigger>
		<Select.Content class="border-cr-border bg-cr-surface max-h-60">
			<Select.Item value="all" class="text-cr-text hover:bg-cr-border">All Servers</Select.Item>
			{#each servers as server (server.id)}
				<Select.Item value={server.id} class="text-cr-text hover:bg-cr-border">
					<span class="flex items-center gap-2">
						<span
							class="inline-flex items-center rounded border px-1 py-0.5 text-xs font-medium"
							style={getProviderBadgeStyle(server.server_type)}
						>
							{server.server_type}
						</span>
						{server.name}
					</span>
				</Select.Item>
			{/each}
		</Select.Content>
	</Select.Root>

	<!-- Invitation filter -->
	{#if invitations.length > 0}
		<Select.Root type="single" value={invitationId ?? 'all'} onValueChange={handleInvitationChange}>
			<Select.Trigger
				class="w-36 border-cr-border bg-cr-bg text-cr-text hover:bg-cr-border/50"
				aria-label="Filter by invitation"
			>
				<span class="truncate font-mono text-xs">{selectedInvitationCode}</span>
			</Select.Trigger>
			<Select.Content class="border-cr-border bg-cr-surface max-h-60">
				<Select.Item value="all" class="text-cr-text hover:bg-cr-border"
					>All Invitations</Select.Item
				>
				{#each invitations as invitation (invitation.id)}
					<Select.Item value={invitation.id} class="text-cr-text hover:bg-cr-border">
						<code class="font-mono text-xs">{invitation.code}</code>
					</Select.Item>
				{/each}
			</Select.Content>
		</Select.Root>
	{/if}

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
			{#each sortByOptions as option (option.value)}
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
