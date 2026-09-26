<script lang="ts">
/**
 * User list page.
 *
 * Displays a paginated, filterable list of users with:
 * - Loading skeleton state during data fetch
 * - Error state with retry functionality
 * - Empty state when no users exist
 * - Table view with status badges and actions
 *
 * @module routes/(admin)/users/+page
 */

import { goto, invalidateAll } from '$app/navigation';
import { page } from '$app/state';
import {
	deleteUser,
	disableUser,
	enableUser,
	type ListUsersParams,
	removeSharedAccess,
	withErrorHandling
} from '$lib/api/client';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import EmptyState from '$lib/components/empty-state.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import Pagination from '$lib/components/pagination.svelte';
import SteppedDeleteDialog from '$lib/components/stepped-delete-dialog.svelte';
import UserFilters from '$lib/components/users/user-filters.svelte';
import UserListSkeleton from '$lib/components/users/user-list-skeleton.svelte';
import UserTable from '$lib/components/users/user-table.svelte';
import { showSuccess } from '$lib/utils/toast';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

// Loading state for refresh operations
let isRefreshing = $state(false);

// Delete state
let deleteTarget = $state<string | null>(null);
let showDeleteDialog = $state(false);
let deleting = $state(false);

// Derive current filter state from URL params
const currentParams = $derived(data.params);

/**
 * Get the user type of the delete target for the stepped dialog.
 */
const deleteTargetType = $derived.by(() => {
	if (!deleteTarget || !data.users) return null;
	const targetUser = data.users.items.find((u) => u.id === deleteTarget);
	return (targetUser?.external_user_type as 'friend' | 'shared' | 'home' | null) ?? null;
});

/**
 * Handle retry after error.
 */
async function handleRetry() {
	isRefreshing = true;
	try {
		await invalidateAll();
	} finally {
		isRefreshing = false;
	}
}

/**
 * Handle filter changes by updating URL params.
 */
function handleFilterChange(newParams: Partial<ListUsersParams>) {
	const url = new URL(page.url);

	// Update or remove each param
	for (const [key, value] of Object.entries(newParams)) {
		if (value === undefined || value === null || value === '') {
			url.searchParams.delete(key);
		} else {
			url.searchParams.set(key, String(value));
		}
	}

	// Reset to page 1 when filters change (except for page changes)
	if (!('page' in newParams)) {
		url.searchParams.set('page', '1');
	}

	goto(url.toString(), { keepFocus: true, noScroll: true });
}

/**
 * Handle page change.
 */
function handlePageChange(newPage: number) {
	handleFilterChange({ page: newPage });
}

/**
 * Handle enabling a user.
 */
async function handleEnableUser(id: string) {
	const result = await withErrorHandling(() => enableUser(id));
	if (!result.error) {
		showSuccess('User enabled');
		await invalidateAll();
	}
}

/**
 * Handle disabling a user.
 */
async function handleDisableUser(id: string) {
	const result = await withErrorHandling(() => disableUser(id));
	if (!result.error) {
		showSuccess('User disabled');
		await invalidateAll();
	}
}

/**
 * Request deletion of a user (shows confirmation dialog).
 */
function handleDeleteRequest(id: string) {
	deleteTarget = id;
	showDeleteDialog = true;
}

/**
 * Handle removing shared access (step 1 for shared users).
 */
async function handleRemoveShares() {
	if (!deleteTarget) return;
	const result = await withErrorHandling(() => removeSharedAccess(deleteTarget!), {
		showErrorToast: false
	});
	if (result.error) {
		throw new Error('Failed to remove shared access');
	}
	showSuccess('Shared access removed');
	await invalidateAll();
}

/**
 * Confirm and execute user deletion (final step).
 */
async function handleDeleteConfirm() {
	if (!deleteTarget) return;
	const target = deleteTarget;
	const result = await withErrorHandling(() => deleteUser(target), {
		showErrorToast: false
	});
	if (result.error) {
		throw new Error('Failed to delete user');
	}
	showSuccess('User deleted');
	showDeleteDialog = false;
	deleteTarget = null;
	await invalidateAll();
}
</script>

<div class="space-y-6">
	<!-- Header with description -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<p class="text-cr-text-muted">Manage users across all connected media servers.</p>
	</div>

	<!-- Filters -->
	<UserFilters
		serverId={currentParams.server_id}
		invitationId={currentParams.invitation_id}
		enabled={currentParams.enabled}
		expired={currentParams.expired}
		search={currentParams.search}
		sortBy={currentParams.sort_by ?? 'created_at'}
		sortOrder={currentParams.sort_order ?? 'desc'}
		servers={data.servers}
		invitations={data.invitations}
		onFilterChange={handleFilterChange}
	/>

	<!-- Content area with loading/error/empty/data states -->
	{#if isRefreshing}
		<UserListSkeleton />
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load users'}
			onRetry={handleRetry}
		/>
	{:else if !data.users || data.users.items.length === 0}
		<EmptyState
			title="No users yet"
			description="Users will appear here once they redeem invitation codes and create accounts on your media servers."
		/>
	{:else}
		<!-- User table -->
		<UserTable
			users={data.users.items}
			onEnable={handleEnableUser}
			onDisable={handleDisableUser}
			onDelete={handleDeleteRequest}
		/>

		<!-- Pagination -->
		<Pagination
			page={data.users.page}
			pageSize={data.users.page_size}
			total={data.users.total}
			hasNext={data.users.has_next}
			onPageChange={handlePageChange}
		/>
	{/if}
</div>

<SteppedDeleteDialog
	bind:open={showDeleteDialog}
	userType={deleteTargetType}
	onRemoveShares={handleRemoveShares}
	onDelete={handleDeleteConfirm}
	onCancel={() => {
	showDeleteDialog = false;
	deleteTarget = null;
}}
/>
