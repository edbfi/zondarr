<script lang="ts">
/**
 * Server card component.
 *
 * Displays a media server as a card with:
 * - Server name and type badge
 * - URL
 * - Enabled status
 * - Library count
 *
 * @module $lib/components/servers/server-card
 */

import { Database, ExternalLink, Server } from '@lucide/svelte';
import type { MediaServerWithLibrariesResponse } from '$lib/api/client';
import StatusBadge from '$lib/components/status-badge.svelte';
import { Button } from '$lib/components/ui/button';
import * as Card from '$lib/components/ui/card';
import { getProviderBadgeStyle, getProviderLabel } from '$lib/stores/providers.svelte';

interface Props {
	server: MediaServerWithLibrariesResponse;
	onViewDetails: (id: string) => void;
}

const { server, onViewDetails }: Props = $props();

const badgeStyle = $derived(getProviderBadgeStyle(server.server_type));
const serverTypeLabel = $derived(getProviderLabel(server.server_type));

/**
 * Get library count text.
 */
const libraryCountText = $derived.by(() => {
	const count = server.libraries.length;
	if (count === 0) return 'No libraries (sync to populate)';
	return count === 1 ? '1 library' : `${count} libraries`;
});
</script>

<Card.Root
	class="border-cr-border bg-cr-surface transition-colors hover:border-cr-accent/30 overflow-hidden"
	data-server-card
	data-server-id={server.id}
>
	<Card.Header class="pb-3">
		<div class="flex items-start justify-between gap-3 min-w-0">
			<div class="flex items-center gap-3 min-w-0">
				<div class="rounded-lg bg-cr-accent/10 p-2 flex-shrink-0">
					<Server class="size-5 text-cr-accent" />
				</div>
				<div class="min-w-0">
					<Card.Title class="text-cr-text text-lg truncate" data-field="name"
						>{server.name}</Card.Title
					>
					<div class="flex items-center gap-2 mt-1">
						<span
							class="inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium"
							style={badgeStyle}
							data-field="server_type"
						>
							{serverTypeLabel}
						</span>
					</div>
				</div>
			</div>
			<span data-field="enabled">
				<StatusBadge
					status={server.enabled ? 'active' : 'disabled'}
					label={server.enabled ? 'Enabled' : 'Disabled'}
				/>
			</span>
		</div>
	</Card.Header>
	<Card.Content class="space-y-4">
		<!-- URL -->
		<div class="flex items-center gap-2 text-sm">
			<ExternalLink class="size-4 text-cr-text-muted flex-shrink-0" />
			<span class="font-mono text-cr-text-muted truncate" data-field="url">{server.url}</span>
		</div>

		<!-- Library count -->
		<div class="flex items-center gap-2 text-sm">
			<Database class="size-4 text-cr-text-muted flex-shrink-0" />
			<span class="text-cr-text" data-field="library_count">{libraryCountText}</span>
		</div>
	</Card.Content>
	<Card.Footer class="pt-3 border-t border-cr-border">
		<Button
			variant="outline"
			size="sm"
			onclick={() => onViewDetails(server.id)}
			class="w-full border-cr-border text-cr-text hover:bg-cr-border"
		>
			View Details
		</Button>
	</Card.Footer>
</Card.Root>
