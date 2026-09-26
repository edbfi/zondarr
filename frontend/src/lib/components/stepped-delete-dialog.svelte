<script lang="ts">
import { AlertTriangle, ChevronRight } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';

type UserType = 'friend' | 'shared' | 'home' | null | undefined;

interface Props {
	open: boolean;
	userType: UserType;
	onRemoveShares: () => Promise<void>;
	onDelete: () => Promise<void>;
	onCancel: () => void;
}

let { open = $bindable(false), userType, onRemoveShares, onDelete, onCancel }: Props = $props();

/** Current step: "shares" for removing shared access, "delete" for final deletion */
let step = $state<'shares' | 'delete'>('shares');
let loading = $state(false);
let error = $state<string | null>(null);

/** Whether this flow has two steps (shared users start with share removal) */
const isTwoStep = $derived(userType === 'shared');

/** Reset state when dialog opens */
$effect(() => {
	if (open) {
		step = isTwoStep ? 'shares' : 'delete';
		loading = false;
		error = null;
	}
});

const title = $derived.by(() => {
	if (step === 'shares') return 'Remove Shared Access';
	switch (userType) {
		case 'friend':
			return 'Remove Friend';
		case 'shared':
			return 'Remove Friend';
		case 'home':
			return 'Remove from Plex Home';
		default:
			return 'Delete User';
	}
});

const description = $derived.by(() => {
	if (step === 'shares') {
		return 'This will remove shared library access for this user on the media server. The friend connection will remain. You can choose to remove the friend connection in the next step.';
	}
	switch (userType) {
		case 'friend':
			return 'This will remove the friend connection on Plex and delete the local database record. This action cannot be undone.';
		case 'shared':
			return 'This will remove the friend connection on Plex and delete the local database record. This action cannot be undone. You can cancel to keep them as a friend.';
		case 'home':
			return 'This will remove this user from Plex Home and delete the local database record. This action cannot be undone.';
		default:
			return 'This will remove the user from both the local database and the media server. This action cannot be undone.';
	}
});

const confirmLabel = $derived.by(() => {
	if (loading) return step === 'shares' ? 'Removing...' : 'Deleting...';
	if (step === 'shares') return 'Remove Shared Access';
	return 'Delete User';
});

const stepIndicator = $derived.by(() => {
	if (!isTwoStep) return null;
	return step === 'shares' ? 'Step 1 of 2' : 'Step 2 of 2';
});

async function handleConfirm() {
	loading = true;
	error = null;
	try {
		if (step === 'shares') {
			await onRemoveShares();
			// Move to step 2
			step = 'delete';
		} else {
			await onDelete();
			open = false;
		}
	} catch (e) {
		error = e instanceof Error ? e.message : 'An error occurred';
	} finally {
		loading = false;
	}
}

function handleCancel() {
	if (!loading) {
		open = false;
		onCancel();
	}
}

function handleOpenChange(isOpen: boolean) {
	if (!isOpen && !loading) {
		onCancel();
	}
}
</script>

<Dialog.Root bind:open onOpenChange={handleOpenChange}>
	<Dialog.Content class="border-cr-border bg-cr-surface sm:max-w-md" showCloseButton={!loading}>
		<div class="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
			<!-- Icon -->
			<div class="rounded-full p-3 bg-rose-500/15 text-rose-400">
				<AlertTriangle class="size-6" />
			</div>

			<!-- Content -->
			<div class="flex-1 text-center sm:text-left">
				<Dialog.Header>
					<div class="flex items-center gap-2">
						<Dialog.Title class="text-cr-text">{title}</Dialog.Title>
						{#if stepIndicator}
							<span
								class="text-xs text-cr-text-muted font-medium px-2 py-0.5 rounded bg-cr-border/50"
							>
								{stepIndicator}
							</span>
						{/if}
					</div>
					<Dialog.Description class="text-cr-text-muted">
						{description}
					</Dialog.Description>
				</Dialog.Header>

				{#if error}
					<div
						class="mt-3 rounded border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-400"
					>
						{error}
					</div>
				{/if}

				{#if isTwoStep && step === 'shares'}
					<div class="mt-3 flex items-center gap-2 text-xs text-cr-text-muted">
						<span class="font-medium text-rose-400">Remove shares</span>
						<ChevronRight class="size-3" />
						<span>Remove friend</span>
					</div>
				{:else if isTwoStep && step === 'delete'}
					<div class="mt-3 flex items-center gap-2 text-xs text-cr-text-muted">
						<span class="line-through">Remove shares</span>
						<ChevronRight class="size-3" />
						<span class="font-medium text-rose-400">Remove friend</span>
					</div>
				{/if}
			</div>
		</div>

		<Dialog.Footer class="mt-6">
			<Button
				variant="outline"
				onclick={handleCancel}
				disabled={loading}
				class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
			>
				Cancel
			</Button>
			<Button
				onclick={handleConfirm}
				disabled={loading}
				class="bg-rose-500 hover:bg-rose-600 text-white"
			>
				{#if loading}
					<span
						class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
					></span>
				{/if}
				{confirmLabel}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
