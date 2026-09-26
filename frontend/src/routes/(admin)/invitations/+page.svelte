<script lang="ts">
/**
 * Invitation list page.
 *
 * Displays a paginated, filterable list of invitations with:
 * - Loading skeleton state during data fetch
 * - Error state with retry functionality
 * - Empty state when no invitations exist
 * - Table view with status badges and actions
 *
 * @module routes/(admin)/invitations/+page
 */

import { goto, invalidateAll } from '$app/navigation';
import { page } from '$app/state';
import { deleteInvitation, type ListInvitationsParams, withErrorHandling } from '$lib/api/client';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import ConfirmDialog from '$lib/components/confirm-dialog.svelte';
import EmptyState from '$lib/components/empty-state.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import CreateInvitationDialog from '$lib/components/invitations/create-invitation-dialog.svelte';
import InvitationFilters from '$lib/components/invitations/invitation-filters.svelte';
import InvitationListSkeleton from '$lib/components/invitations/invitation-list-skeleton.svelte';
import InvitationTable from '$lib/components/invitations/invitation-table.svelte';
import Pagination from '$lib/components/pagination.svelte';
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
function handleFilterChange(newParams: Partial<ListInvitationsParams>) {
	const url = new URL(page.url);

	// Update or remove each param
	for (const [key, value] of Object.entries(newParams)) {
		if (value === undefined || value === null) {
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
 * Request deletion of an invitation (shows confirmation dialog).
 */
function handleDeleteRequest(id: string) {
	deleteTarget = id;
	showDeleteDialog = true;
}

/**
 * Confirm and execute invitation deletion.
 */
async function handleDeleteConfirm() {
	if (!deleteTarget) return;
	const target = deleteTarget;
	deleting = true;
	try {
		const result = await withErrorHandling(() => deleteInvitation(target));
		if (!result.error) {
			showSuccess('Invitation deleted');
			await invalidateAll();
		}
	} finally {
		deleting = false;
		showDeleteDialog = false;
		deleteTarget = null;
	}
}
</script>

<div class="space-y-6">
	<!-- Header with description and create button -->
	<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
		<p class="text-cr-text-muted">Manage invitation codes for user onboarding.</p>
		<CreateInvitationDialog servers={data.servers} onSuccess={() => invalidateAll()} />
	</div>

	<!-- Filters -->
	<InvitationFilters
		enabled={currentParams.enabled}
		expired={currentParams.expired}
		sortBy={currentParams.sort_by ?? 'created_at'}
		sortOrder={currentParams.sort_order ?? 'desc'}
		onFilterChange={handleFilterChange}
	/>

	<!-- Content area with loading/error/empty/data states -->
	{#if isRefreshing}
		<InvitationListSkeleton />
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load invitations'}
			onRetry={handleRetry}
		/>
	{:else if !data.invitations || data.invitations.items.length === 0}
		<EmptyState
			title="No invitations yet"
			description="Create your first invitation using the button above to start onboarding users to your media servers."
		/>
	{:else}
		<!-- Invitation table -->
		<InvitationTable invitations={data.invitations.items} onDelete={handleDeleteRequest} />

		<!-- Pagination -->
		<Pagination
			page={data.invitations.page}
			pageSize={data.invitations.page_size}
			total={data.invitations.total}
			hasNext={data.invitations.has_next}
			onPageChange={handlePageChange}
		/>
	{/if}
</div>

<ConfirmDialog
	open={showDeleteDialog}
	title="Delete Invitation"
	description="Are you sure you want to delete this invitation? This action cannot be undone."
	confirmLabel={deleting ? 'Deleting...' : 'Delete'}
	variant="destructive"
	loading={deleting}
	onConfirm={handleDeleteConfirm}
	onCancel={() => {
	showDeleteDialog = false;
	deleteTarget = null;
}}
/>
