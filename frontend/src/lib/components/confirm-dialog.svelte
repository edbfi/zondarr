<script lang="ts">
import { AlertTriangle } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import { cn } from '$lib/utils.js';

interface Props {
	open: boolean;
	title: string;
	description: string;
	confirmLabel?: string;
	cancelLabel?: string;
	variant?: 'destructive' | 'warning' | 'default';
	onConfirm: () => void;
	onCancel: () => void;
	loading?: boolean;
}

let {
	open = $bindable(false),
	title,
	description,
	confirmLabel = 'Confirm',
	cancelLabel = 'Cancel',
	variant = 'destructive',
	onConfirm,
	onCancel,
	loading = false
}: Props = $props();

// Derive icon and button styles based on variant
const iconClass = $derived.by(() => {
	switch (variant) {
		case 'destructive':
			return 'bg-rose-500/15 text-rose-400';
		case 'warning':
			return 'bg-amber-500/15 text-amber-400';
		default:
			return 'bg-cr-accent/15 text-cr-accent';
	}
});

const confirmButtonClass = $derived.by(() => {
	switch (variant) {
		case 'destructive':
			return 'bg-rose-500 hover:bg-rose-600 text-white';
		case 'warning':
			return 'bg-amber-500 hover:bg-amber-600 text-white';
		default:
			return 'bg-cr-accent hover:bg-cr-accent-hover text-cr-bg';
	}
});

function handleConfirm() {
	onConfirm();
}

function handleCancel() {
	open = false;
	onCancel();
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
			<div class={cn('rounded-full p-3', iconClass)}>
				<AlertTriangle class="size-6" />
			</div>

			<!-- Content -->
			<div class="flex-1 text-center sm:text-left">
				<Dialog.Header>
					<Dialog.Title class="text-cr-text">{title}</Dialog.Title>
					<Dialog.Description class="text-cr-text-muted">
						{description}
					</Dialog.Description>
				</Dialog.Header>
			</div>
		</div>

		<Dialog.Footer class="mt-6">
			<Button
				variant="outline"
				onclick={handleCancel}
				disabled={loading}
				class="border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
			>
				{cancelLabel}
			</Button>
			<Button onclick={handleConfirm} disabled={loading} class={confirmButtonClass}>
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
