<script lang="ts">
import { Clock, Server, Ticket, Users } from '@lucide/svelte';
import { invalidateAll } from '$app/navigation';
import { getErrorMessage, isNetworkError } from '$lib/api/errors';
import DashboardSkeleton from '$lib/components/dashboard/dashboard-skeleton.svelte';
import RecentActivity from '$lib/components/dashboard/recent-activity.svelte';
import StatCard from '$lib/components/dashboard/stat-card.svelte';
import ErrorState from '$lib/components/error-state.svelte';
import type { PageData } from './$types';

const { data }: { data: PageData } = $props();

let isRefreshing = $state(false);

async function handleRetry() {
	isRefreshing = true;
	try {
		await invalidateAll();
	} finally {
		isRefreshing = false;
	}
}
</script>

<div class="space-y-6">
	{#if isRefreshing}
		<DashboardSkeleton />
	{:else if data.error}
		<ErrorState
			message={getErrorMessage(data.error)}
			title={isNetworkError(data.error) ? 'Connection Error' : 'Failed to load dashboard'}
			onRetry={handleRetry}
		/>
	{:else if data.stats}
		<!-- Stat cards grid -->
		<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
			<StatCard
				title="Total Invitations"
				value={data.stats.total_invitations}
				subtitle="{data.stats.active_invitations} currently active"
				accentClass="text-cr-accent"
			>
				{#snippet icon()}
					<Ticket class="size-5" />
				{/snippet}
			</StatCard>

			<StatCard
				title="Active Users"
				value={data.stats.active_users}
				subtitle="of {data.stats.total_users} total"
				accentClass="text-cr-active"
			>
				{#snippet icon()}
					<Users class="size-5" />
				{/snippet}
			</StatCard>

			<StatCard
				title="Media Servers"
				value={data.stats.total_servers}
				subtitle="{data.stats.enabled_servers} enabled"
				accentClass="text-violet-400"
			>
				{#snippet icon()}
					<Server class="size-5" />
				{/snippet}
			</StatCard>

			<StatCard
				title="Pending Invites"
				value={data.stats.pending_invitations}
				subtitle={data.stats.pending_invitations > 0 ? 'awaiting first use' : undefined}
				accentClass="text-cr-pending"
			>
				{#snippet icon()}
					<Clock class="size-5" />
				{/snippet}
			</StatCard>
		</div>

		<!-- Recent activity -->
		<RecentActivity activities={data.stats.recent_activity} />
	{/if}
</div>
