const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// tsconfigPaths lets Metro resolve the "@/*" alias declared in tsconfig.json.
config.resolver.unstable_enablePackageExports = true;

module.exports = config;
