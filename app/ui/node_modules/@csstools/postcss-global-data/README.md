# PostCSS Global Data [<img src="https://postcss.github.io/postcss/logo.svg" alt="PostCSS Logo" width="90" height="90" align="right">][PostCSS]

`npm install @csstools/postcss-global-data --save-dev`

[PostCSS Global Data] lets you inject CSS that is removed again before the final output. This is useful for  plugins that use global CSS as data.

For example, in the case of CSS Modules with [PostCSS Custom Media](https://github.com/csstools/postcss-plugins/tree/main/plugins/postcss-custom-media), rules are usually not imported by every single file, so PostCSS Custom Media cannot generate fallbacks.
By providing a list of files, this plugin will inject the global CSS as data so that PostCSS Custom Media can generate fallbacks.

It is important that [PostCSS Global Data] is used before the plugin that actually needs the data.

Please note that [PostCSS Global Data] does not add anything to the output of your CSS. It only injects data into PostCSS so that other plugins
can actually use it.

## Usage

Add [PostCSS Global Data] to your project:

```bash
npm install postcss @csstools/postcss-global-data --save-dev
```

Use it as a [PostCSS] plugin:

```js
const postcss = require('postcss');
const postcssGlobalData = require('@csstools/postcss-global-data');

postcss([
	postcssGlobalData(/* pluginOptions */)
]).process(YOUR_CSS /*, processOptions */);
```



## Options

### `files`

The `files` option determines which files to inject into PostCSS.

```js
postcssGlobalData({ 
	files: [
		'./src/css/variables.css',
		'./src/css/media-queries.css',
	],
});
```

### Plugin order control with `lateRemover`

The `lateRemover` option gives you more options when ordering plugins.

```js
// esm
import postcss from 'postcss';
import postcssGlobalData from '@csstools/postcss-global-data';

const [globalData, globalDataLateRemover] = postcssGlobalData({ 
	files: [
		'./src/css/variables.css',
		'./src/css/media-queries.css',
	],
	lateRemover: true
}).plugins

postcss([
	globalData,
	/* other plugins */
	globalDataLateRemover
]).process(YOUR_CSS /*, processOptions */);
```

### `prepend`

The `prepend` option determines if injected CSS is appended or prepended.  
Defaults to `false`.

> [!Warning]
> Prepending styles before `@import` statements will create broken stylesheets.

```js
postcssGlobalData({ 
	files: [
		'./src/css/variables.css',
		'./src/css/media-queries.css',
	],
	prepend: true
});
```

[cli-url]: https://github.com/csstools/postcss-plugins/actions/workflows/test.yml?query=workflow/test

[discord]: https://discord.gg/bUadyRwkJS
[npm-url]: https://www.npmjs.com/package/@csstools/postcss-global-data

[PostCSS]: https://github.com/postcss/postcss
[PostCSS Global Data]: https://github.com/csstools/postcss-plugins/tree/main/plugins/postcss-global-data
