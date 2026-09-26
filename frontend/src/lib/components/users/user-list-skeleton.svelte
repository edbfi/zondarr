<script lang="ts">
/**
 * Skeleton loading state for user list.
 *
 * Displays a shimmer animation while user data is loading.
 * Matches the structure of the actual user table.
 */

import { Skeleton } from '$lib/components/ui/skeleton';
import * as Table from '$lib/components/ui/table';
</script>

<div class="rounded-lg border border-cr-border bg-cr-surface">
	<Table.Root>
		<Table.Header>
			<Table.Row class="border-cr-border hover:bg-transparent">
				<Table.Head class="text-cr-text-muted">Username</Table.Head>
				<Table.Head class="text-cr-text-muted">Server</Table.Head>
				<Table.Head class="text-cr-text-muted">Status</Table.Head>
				<Table.Head class="text-cr-text-muted hidden sm:table-cell">Expires</Table.Head>
				<Table.Head class="text-cr-text-muted hidden md:table-cell">Created</Table.Head>
				<Table.Head class="text-cr-text-muted hidden lg:table-cell">Invitation</Table.Head>
				<Table.Head class="text-cr-text-muted text-right">Actions</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each Array(5) as _, i (i)}
				<Table.Row class="border-cr-border">
					<Table.Cell>
						<Skeleton class="h-5 w-28 bg-cr-border" />
					</Table.Cell>
					<Table.Cell>
						<Skeleton class="h-5 w-24 bg-cr-border" />
					</Table.Cell>
					<Table.Cell>
						<Skeleton class="h-5 w-16 rounded-full bg-cr-border" />
					</Table.Cell>
					<Table.Cell class="hidden sm:table-cell">
						<Skeleton class="h-5 w-28 bg-cr-border" />
					</Table.Cell>
					<Table.Cell class="hidden md:table-cell">
						<Skeleton class="h-5 w-28 bg-cr-border" />
					</Table.Cell>
					<Table.Cell class="hidden lg:table-cell">
						<Skeleton class="h-5 w-20 bg-cr-border" />
					</Table.Cell>
					<Table.Cell class="text-right">
						<Skeleton class="ml-auto h-8 w-8 bg-cr-border" />
					</Table.Cell>
				</Table.Row>
			{/each}
		</Table.Body>
	</Table.Root>
</div>
