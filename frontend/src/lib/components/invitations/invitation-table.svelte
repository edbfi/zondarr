<script lang="ts">
/**
 * Invitation table component.
 *
 * Displays a list of invitations in a table format with:
 * - Code (monospace font)
 * - Status badge (active/pending/disabled/expired)
 * - Use count and remaining uses
 * - Expiration date
 * - Created date
 * - Action buttons
 *
 * @module $lib/components/invitations/invitation-table
 */

import type { InvitationResponse } from '$lib/api/client';
import * as Table from '$lib/components/ui/table';
import InvitationRow from './invitation-row.svelte';

interface Props {
	invitations: InvitationResponse[];
	onEdit?: (id: string) => void;
	onDelete?: (id: string) => void;
}

const { invitations, onEdit, onDelete }: Props = $props();
</script>

<div class="rounded-lg border border-cr-border bg-cr-surface" data-invitation-table>
	<Table.Root>
		<Table.Header>
			<Table.Row class="border-cr-border hover:bg-transparent">
				<Table.Head class="text-cr-text-muted">Code</Table.Head>
				<Table.Head class="text-cr-text-muted">Status</Table.Head>
				<Table.Head class="text-cr-text-muted">Uses</Table.Head>
				<Table.Head class="text-cr-text-muted hidden sm:table-cell">Expires</Table.Head>
				<Table.Head class="text-cr-text-muted hidden md:table-cell">Created</Table.Head>
				<Table.Head class="text-cr-text-muted text-right">Actions</Table.Head>
			</Table.Row>
		</Table.Header>
		<Table.Body>
			{#each invitations as invitation (invitation.id)}
				<InvitationRow {invitation} {onEdit} {onDelete} />
			{/each}
		</Table.Body>
	</Table.Root>
</div>
