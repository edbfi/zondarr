<script lang="ts">
import ErrorBoundary from './error-boundary.svelte';

let errorBoundaryRef: ReturnType<typeof ErrorBoundary> | undefined = $state();

export function triggerError(error: Error) {
	if (errorBoundaryRef) {
		errorBoundaryRef.handleError(error);
	}
}
</script>

<ErrorBoundary bind:this={errorBoundaryRef}>
	{#snippet children()}
		<div data-testid="test-content">Test Content</div>
	{/snippet}
</ErrorBoundary>
