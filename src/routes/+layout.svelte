<script lang="ts">
import "../app.css";
// The bundled fonts (DESIGN.md: no remote font requests). Outfit's variable package holds every
// subset behind `unicode-range`; Plex Mono is static, so only the weight the `code` style uses.
import "@fontsource-variable/outfit";
import "@fontsource/ibm-plex-mono/400.css";
import { onMount } from "svelte";
import type { LayoutProps } from "./$types";

let { children }: LayoutProps = $props();

// A client-side signal that the app has hydrated, for the e2e tests to wait on.
onMount(() => {
	document.documentElement.dataset.hydrated = "";
});
</script>

{@render children()}
