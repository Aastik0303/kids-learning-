module.exports = function babelConfig(api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    // Path aliases (@/*) come from tsconfig `paths`, which Expo's Metro
    // resolves natively — no module-resolver plugin needed.
    // Reanimated 4 ships its worklet transform through react-native-worklets
    // and it must stay last in the plugin list.
    plugins: ["react-native-worklets/plugin"],
  };
};
