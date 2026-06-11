---
name: Soft Iridescence
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#494454'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#7b7486'
  outline-variant: '#cbc3d7'
  surface-tint: '#6d3bd7'
  primary: '#6b38d4'
  on-primary: '#ffffff'
  primary-container: '#8455ef'
  on-primary-container: '#fffbff'
  inverse-primary: '#d0bcff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#00628d'
  on-tertiary: '#ffffff'
  tertiary-container: '#007cb1'
  on-tertiary-container: '#fcfcff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e9ddff'
  primary-fixed-dim: '#d0bcff'
  on-primary-fixed: '#23005c'
  on-primary-fixed-variant: '#5516be'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#c9e6ff'
  tertiary-fixed-dim: '#89ceff'
  on-tertiary-fixed: '#001e2f'
  on-tertiary-fixed-variant: '#004c6e'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '600'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-xl-mobile:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '500'
    lineHeight: '1.3'
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: '0'
  body-md:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
    letterSpacing: '0'
  label-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1'
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-max: 1200px
  gutter: 32px
  margin-desktop: 64px
  margin-mobile: 24px
  section-gap: 128px
---

## Brand & Style
The brand personality is ethereal, calm, and highly focused. This design system prioritizes cognitive ease and a sense of "airiness" to create an environment where content feels like it is floating within a light-filled space. The target audience includes creative professionals, wellness-tech users, and those seeking a premium, meditative digital experience.

The design style is a hybrid of **Minimalism** and **Glassmorphism**. It utilizes extreme whitespace to define structure rather than heavy lines. Depth is achieved through "mesh" blurred backgrounds and semi-transparent layers that allow soft, iridescent colors to bleed through surfaces, mimicking the behavior of light passing through frosted glass or thin fabric.

## Colors
The palette is rooted in high-luminance pastels that provide a sense of freshness without visual fatigue. 

- **Primary (Lavender):** Used for key interactive states and subtle focus indicators.
- **Secondary (Mint):** Reserved for success states and secondary highlights to maintain a natural, organic feel.
- **Tertiary (Sky Blue):** Utilized for informational elements and link highlights.
- **Neutral:** A range of cool whites and soft slates that form the "canvas" of the UI.

Mesh gradients should be generated using low-saturation versions of the primary, secondary, and tertiary colors, blurred at a radius of 120px or higher to create a soft, non-distracting background glow.

## Typography
This design system employs **Geist** for its technical precision and clean, geometric proportions. The typography is treated with generous leading (line height) to reinforce the "breathable" narrative. 

Headlines use tight letter spacing and heavier weights to provide a grounding contrast to the light UI, while body text remains open and legible. For mobile, headline sizes are aggressively scaled down to ensure they do not overwhelm the compact viewport. Label styles should be used sparingly for metadata and small UI controls, often with a slight increase in letter spacing for clarity.

## Layout & Spacing
The layout follows a **Fluid Grid** philosophy with exceptionally wide margins and gutters to ensure content never feels cramped. 

- **Desktop:** A 12-column grid with 32px gutters. Large sections are separated by a "Section Gap" of 128px to force a slow, intentional scroll.
- **Tablet:** 8-column grid with 24px gutters. 
- **Mobile:** 4-column grid with 16px gutters and 24px side margins.

Horizontal padding within components (like cards or inputs) should always be greater than vertical padding to maintain a sleek, elongated aesthetic.

## Elevation & Depth
Depth is created through **Tonal Layers** and **Glassmorphism** rather than traditional shadows.

1.  **Base Layer:** Solid `#FFFFFF` or a very faint mesh gradient.
2.  **Surface Layer:** Semi-transparent white (`rgba(255, 255, 255, 0.7)`) with a `backdrop-filter: blur(20px)`.
3.  **Floating Elements:** Used for modals or menus, these utilize a "Micro-Shadow"—an extremely light, wide-spread shadow (`0 20px 40px rgba(0, 0, 0, 0.03)`) to suggest a gentle lift off the page.

Avoid solid borders; instead, use a 1px inner stroke with 10% opacity white to define edges on glass surfaces.

## Shapes
Shapes are intentionally soft to harmonize with the "breathable" theme. The standard corner radius is 0.5rem (8px), which provides enough curvature to feel friendly without becoming overly juvenile. 

For larger containers like cards and featured image blocks, use the `rounded-xl` (1.5rem/24px) setting to create a more distinct, pillowed appearance. Interactive elements like "pill" buttons may occasionally override these defaults to use a fully circular radius.

## Components
- **Buttons:** Primary buttons use a soft lavender gradient. Secondary buttons are "ghost" style with a 1px semi-transparent border. All buttons have a high horizontal padding (at least 2x the vertical padding).
- **Cards:** Cards should have no visible border. Instead, they use a glassmorphic background blur and a very soft micro-shadow. 
- **Inputs:** Input fields are minimal, featuring only a bottom border that glows with the primary color when focused. The background is a very faint gray (`#F1F5F9`).
- **Chips/Badges:** These are pill-shaped with low-opacity pastel backgrounds (e.g., 10% opacity Lavender for a Lavender-tinted text) to keep them from drawing too much visual weight.
- **Lists:** List items are separated by whitespace rather than lines. Hover states are indicated by a subtle increase in the glassmorphic background opacity.
- **Mesh Backdrops:** Not a functional component, but a required decorative element behind main content areas to reinforce the "Iridescence" theme.