<script lang="ts">
	import { css } from "#styled-system/css";
</script>

<svelte:head>
	<title>Zondarr</title>
</svelte:head>

<!-- Placeholder until the first module gives / a surface (the legacy root sends people to the
     admin sign-in or the dashboard). -->
<main
	class={css({
		maxWidth: "readingMax",
		marginInline: "auto",
		paddingBlock: "hero",
		paddingInline: { base: "mobileGutter", tablet: "tabletGutter", desktop: "desktopGutter" },
	})}
>
	<h1 class={css({ textStyle: "h1", textWrap: "balance" })}>Zondarr is being rebuilt.</h1>
	<p class={css({ marginBlockStart: "lg", color: "muted", textWrap: "pretty" })}>
		The invitation pages and the admin console are on their way back. Invitation links don't open
		yet.
	</p>
</main>
