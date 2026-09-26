<script lang="ts">
import * as Card from '$lib/components/ui/card';
import { Skeleton } from '$lib/components/ui/skeleton';
</script>

<!-- 4 skeleton stat cards -->
<div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
	{#each Array(4) as _, i (i)}
		<Card.Root class="border-cr-border bg-cr-surface">
			<Card.Content class="pt-6">
				<div class="flex items-start justify-between">
					<div class="space-y-2">
						<Skeleton class="h-4 w-24" />
						<Skeleton class="h-8 w-16" />
						<Skeleton class="h-3 w-32" />
					</div>
					<Skeleton class="size-10 rounded-lg" />
				</div>
			</Card.Content>
		</Card.Root>
	{/each}
</div>

<!-- Skeleton activity card -->
<Card.Root class="border-cr-border bg-cr-surface">
	<Card.Header>
		<Skeleton class="h-5 w-32" />
		<Skeleton class="h-4 w-48" />
	</Card.Header>
	<Card.Content>
		<div class="space-y-3">
			{#each Array(5) as _, i (i)}
				<div class="flex items-center gap-3">
					<Skeleton class="size-8 rounded-lg" />
					<Skeleton class="h-4 flex-1" />
					<Skeleton class="h-3 w-12" />
				</div>
			{/each}
		</div>
	</Card.Content>
</Card.Root>
