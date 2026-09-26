<script lang="ts">
import { Moon, Sun } from '@lucide/svelte';
import { mode, toggleMode } from 'mode-watcher';
import { Button } from '$lib/components/ui/button';
</script>

<Button
	variant="ghost"
	size="icon"
	onclick={toggleMode}
	aria-label={mode.current === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
	class="text-cr-text-muted hover:text-cr-accent"
>
	{#if mode.current === 'dark'}
		<Sun class="size-5" />
	{:else}
		<Moon class="size-5" />
	{/if}
</Button>
