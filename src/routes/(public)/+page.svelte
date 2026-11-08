<script lang="ts">
import LanguageSwitcher from "#lib/components/layout/LanguageSwitcher.svelte";
import { m } from "#lib/paraglide/messages.js";
import { css } from "#styled-system/css";
</script>

<svelte:head>
	<title>Zondarr</title>
</svelte:head>

<!-- Placeholder until the first module gives / a surface. -->
<main
	class={css({
		maxWidth: "readingMax",
		marginInline: "auto",
		paddingBlock: "hero",
		paddingInline: { base: "mobileGutter", tablet: "tabletGutter", desktop: "desktopGutter" },
	})}
>
	<LanguageSwitcher />
	<h1 class={css({ textStyle: "h1", marginBlockStart: "xxl", textWrap: "balance" })}>
		{m.placeholder_title()}
	</h1>
	<p class={css({ marginBlockStart: "lg", color: "muted", textWrap: "pretty" })}>
		{m.placeholder_status()}
	</p>
</main>
