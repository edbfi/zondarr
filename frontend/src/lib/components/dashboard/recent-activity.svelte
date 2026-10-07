<script lang="ts">
import { Activity, RefreshCw, Server, Ticket, UserPlus } from '@lucide/svelte';
import type { RecentActivityItem } from '$lib/api/client';
import * as Card from '$lib/components/ui/card';

interface Props {
	activities: RecentActivityItem[];
}

const { activities }: Props = $props();

const activityConfig: Record<string, { icon: typeof UserPlus; colorClass: string }> = {
	user_created: { icon: UserPlus, colorClass: 'text-cr-active' },
	invitation_created: { icon: Ticket, colorClass: 'text-cr-accent' },
	sync_completed: { icon: RefreshCw, colorClass: 'text-violet-400' },
	server_added: { icon: Server, colorClass: 'text-cr-pending' }
};

function formatRelativeTime(date: string | Date): string {
	const now = Date.now();
	const then = new Date(date).getTime();
	const diff = now - then;
	const seconds = Math.floor(diff / 1000);
	if (seconds < 60) return 'just now';
	const minutes = Math.floor(seconds / 60);
	if (minutes < 60) return `${minutes}m ago`;
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	const days = Math.floor(hours / 24);
	if (days < 30) return `${days}d ago`;
	return new Date(date).toLocaleDateString();
}
</script>

<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<Card.Title class="text-lg font-display text-cr-text">Recent Activity</Card.Title>
		<Card.Description class="text-cr-text-muted">
			Latest events across your media servers
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if activities.length === 0}
			<div class="flex flex-col items-center justify-center py-8 text-cr-text-muted">
				<Activity class="size-8 mb-2 opacity-50" />
				<p class="text-sm">No recent activity to display</p>
			</div>
		{:else}
			<div class="space-y-0 divide-y divide-cr-border">
				{#each activities as activity}
					{@const config = activityConfig[activity.type]}
					<div class="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
						<div
							class={`rounded-lg p-2 bg-current/10 ${config?.colorClass ?? 'text-cr-text-muted'}`}
						>
							{#if config}
								<config.icon class="size-4" />
							{:else}
								<Activity class="size-4" />
							{/if}
						</div>
						<div class="flex-1 min-w-0">
							<p class="text-sm text-cr-text truncate">{activity.description}</p>
						</div>
						<time class="text-xs text-cr-text-dim whitespace-nowrap font-data">
							{formatRelativeTime(activity.timestamp)}
						</time>
					</div>
				{/each}
			</div>
		{/if}
	</Card.Content>
</Card.Root>
