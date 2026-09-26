<script lang="ts">
import type { Snippet } from 'svelte';

interface Props {
	children: Snippet;
}

const { children }: Props = $props();
</script>

<h1 class="text-xl font-semibold font-display text-cr-text tracking-tight">
	{@render children()}
</h1>
