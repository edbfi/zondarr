<script lang="ts">
/**
 * User table component.
 *
 * Displays a list of users in a table format with:
 * - Username
 * - Media server name
 * - Status badge (enabled/disabled/expired)
 * - Expiration date
 * - Created date
 * - Source invitation code (if available)
 * - Action buttons
 *
 * @module $lib/components/users/user-table
 */

import type { UserDetailResponse } from '$lib/api/client';
import * as Table from '$lib/components/ui/table';
import UserRow from './user-row.svelte';

interface Props {
	users: UserDetailResponse[];
	onEnable?: (id: string) => void;
	onDisable?: (id: string) => void;
	onDelete?: (id: string) => void;
}

const { users, onEnable, onDisable, onDelete }: Props = $props();
</script>

<div class="rounded-lg border border-cr-border bg-cr-surface" data-user-table>
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
			{#each users as user (user.id)}
				<UserRow {user} {onEnable} {onDisable} {onDelete} />
			{/each}
		</Table.Body>
	</Table.Root>
</div>
