<script lang="ts">
import { AlertTriangle, RefreshCw } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';
import { cn } from '$lib/utils.js';

interface Props {
	message: string;
	title?: string;
	onRetry?: () => void;
	class?: string;
}

const { message, title = 'Something went wrong', onRetry, class: className }: Props = $props();
</script>

<div
	data-error-state
	class={cn(
	'flex flex-col items-center justify-center rounded-lg border border-rose-500/30 bg-rose-500/5 px-6 py-12 text-center',
	className
)}
	role="alert"
	aria-live="polite"
>
	<!-- Icon -->
	<div class="mb-4 rounded-full bg-rose-500/15 p-3 text-rose-400">
		<AlertTriangle class="size-8" />
	</div>

	<!-- Title -->
	<h3 class="text-lg font-semibold text-cr-text">{title}</h3>

	<!-- Error message -->
	<p class="mt-1 max-w-md text-sm text-cr-text-muted">{message}</p>

	<!-- Retry button -->
	{#if onRetry}
		<Button
			onclick={onRetry}
			variant="outline"
			class="mt-4 border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
		>
			<RefreshCw class="size-4" />
			Try again
		</Button>
	{/if}
</div>
