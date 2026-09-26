<script lang="ts">
import { AlertTriangle, RefreshCw } from '@lucide/svelte';
import type { Snippet } from 'svelte';
import { Button } from '$lib/components/ui/button';
import { cn } from '$lib/utils.js';

interface Props {
	children: Snippet;
	fallback?: Snippet<[{ error: Error; reset: () => void }]>;
	class?: string;
}

const { children, fallback, class: className }: Props = $props();

let error = $state<Error | null>(null);

/**
 * Handle an error caught by the boundary.
 * Call this from child components via context or event.
 */
export function handleError(e: Error) {
	error = e;
	console.error('Error boundary caught:', e);
}

/**
 * Reset the error state to re-render children.
 */
function reset() {
	error = null;
}
</script>

{#if error}
	{#if fallback}
		{@render fallback({ error, reset })}
	{:else}
		<div
			class={cn(
	'flex flex-col items-center justify-center rounded-lg border border-rose-500/30 bg-rose-500/5 px-6 py-12 text-center',
	className
)}
			role="alert"
			aria-live="polite"
		>
			<div class="mb-4 rounded-full bg-rose-500/15 p-3 text-rose-400">
				<AlertTriangle class="size-8" />
			</div>

			<h3 class="text-lg font-semibold text-cr-text">Something went wrong</h3>

			<p class="mt-1 max-w-md text-sm text-cr-text-muted">
				An unexpected error occurred. Please try again.
			</p>

			<Button
				onclick={reset}
				variant="outline"
				class="mt-4 border-cr-border bg-cr-surface hover:bg-cr-border text-cr-text"
			>
				<RefreshCw class="size-4" />
				Try again
			</Button>
		</div>
	{/if}
{:else}
	{@render children()}
{/if}
