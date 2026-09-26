<script lang="ts">
/**
 * Server list skeleton component.
 *
 * Displays loading skeleton cards while server data is being fetched.
 *
 * @module $lib/components/servers/server-list-skeleton
 */

import * as Card from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
</script>

<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
	{#each Array(3) as _, i (i)}
		<Card.Root class="border-cr-border bg-cr-surface">
			<Card.Header class="pb-3">
				<div class="flex items-start justify-between gap-3">
					<div class="flex items-center gap-3">
						<Skeleton class="size-9 rounded-lg" />
						<div class="space-y-2">
							<Skeleton class="h-5 w-32" />
							<Skeleton class="h-4 w-16" />
						</div>
					</div>
					<Skeleton class="h-5 w-16 rounded-full" />
				</div>
			</Card.Header>
			<Card.Content class="space-y-4">
				<div class="flex items-center gap-2">
					<Skeleton class="size-4" />
					<Skeleton class="h-4 w-48" />
				</div>
				<div class="flex items-center gap-2">
					<Skeleton class="size-4" />
					<Skeleton class="h-4 w-24" />
				</div>
			</Card.Content>
			<Card.Footer class="pt-3 border-t border-cr-border">
				<Skeleton class="h-8 w-full" />
			</Card.Footer>
		</Card.Root>
	{/each}
</div>
