<script setup lang="ts">
/**
 * Logo 组件：使用内联 SVG 版本，便于 currentColor 跟随主题色。
 *
 * variant:
 *  - 'mark'  仅图形（正方形，用于小尺寸 / favicon 场景）
 *  - 'full'  图形 + 汉字（横向，用于导航头）
 *
 * size 是像素高度；'full' 的宽高比约 200:56。
 */
withDefaults(defineProps<{
  variant?: 'mark' | 'full'
  size?: number
  /** 覆盖颜色。默认从父容器继承（通过 currentColor） */
  color?: string
}>(), {
  variant: 'mark',
  size: 24,
})
</script>

<template>
  <!-- 图形 mark -->
  <svg
    v-if="variant === 'mark'"
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 64 64"
    fill="none"
    :style="{ width: size + 'px', height: size + 'px', color }"
    role="img"
    aria-label="梦蝶"
  >
    <defs>
      <linearGradient :id="`mengdie-mark-${size}-a`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.28" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0.08" />
      </linearGradient>
      <linearGradient :id="`mengdie-mark-${size}-b`" x1="1" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.28" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0.08" />
      </linearGradient>
    </defs>
    <g stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M32 32 C 20 12, 8 18, 10 30 C 12 40, 22 38, 32 32 Z" :fill="`url(#mengdie-mark-${size}-a)`" />
      <path d="M32 32 C 44 12, 56 18, 54 30 C 52 40, 42 38, 32 32 Z" :fill="`url(#mengdie-mark-${size}-b)`" />
      <path d="M32 32 C 22 42, 14 50, 20 55 C 26 58, 30 50, 32 42 Z" :fill="`url(#mengdie-mark-${size}-a)`" />
      <path d="M32 32 C 42 42, 50 50, 44 55 C 38 58, 34 50, 32 42 Z" :fill="`url(#mengdie-mark-${size}-b)`" />
      <path d="M32 20 L 32 46" stroke-width="2.2" />
      <path d="M32 20 C 30 15, 27 13, 25 12" fill="none" />
      <path d="M32 20 C 34 15, 37 13, 39 12" fill="none" />
      <circle cx="25" cy="12" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="39" cy="12" r="1.1" fill="currentColor" stroke="none" />
    </g>
  </svg>

  <!-- 图形 + 文字 -->
  <svg
    v-else
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 200 56"
    fill="none"
    :style="{ height: size + 'px', color }"
    role="img"
    aria-label="梦蝶"
  >
    <defs>
      <linearGradient :id="`mengdie-full-${size}-a`" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.28" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0.08" />
      </linearGradient>
      <linearGradient :id="`mengdie-full-${size}-b`" x1="1" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.28" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0.08" />
      </linearGradient>
    </defs>
    <g transform="scale(0.875)" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M32 32 C 20 12, 8 18, 10 30 C 12 40, 22 38, 32 32 Z" :fill="`url(#mengdie-full-${size}-a)`" />
      <path d="M32 32 C 44 12, 56 18, 54 30 C 52 40, 42 38, 32 32 Z" :fill="`url(#mengdie-full-${size}-b)`" />
      <path d="M32 32 C 22 42, 14 50, 20 55 C 26 58, 30 50, 32 42 Z" :fill="`url(#mengdie-full-${size}-a)`" />
      <path d="M32 32 C 42 42, 50 50, 44 55 C 38 58, 34 50, 32 42 Z" :fill="`url(#mengdie-full-${size}-b)`" />
      <path d="M32 20 L 32 46" stroke-width="2.4" />
      <path d="M32 20 C 30 15, 27 13, 25 12" fill="none" />
      <path d="M32 20 C 34 15, 37 13, 39 12" fill="none" />
      <circle cx="25" cy="12" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="39" cy="12" r="1.2" fill="currentColor" stroke="none" />
    </g>
    <text
      x="66" y="30"
      font-family="'PingFang SC', 'HarmonyOS Sans SC', 'Microsoft YaHei', sans-serif"
      font-size="22" font-weight="600" letter-spacing="2"
      fill="currentColor"
    >梦蝶</text>
    <text
      x="66" y="46"
      font-family="'JetBrains Mono', 'SF Mono', 'Menlo', monospace"
      font-size="10" letter-spacing="1.5"
      fill="currentColor" opacity="0.5"
    >mèng dié</text>
  </svg>
</template>
