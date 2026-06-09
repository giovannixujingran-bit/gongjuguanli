---
name: Deep Tech Minimalist
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#191c1e'
  on-tertiary-container: '#818486'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#e0e3e5'
  tertiary-fixed-dim: '#c4c7c9'
  on-tertiary-fixed: '#191c1e'
  on-tertiary-fixed-variant: '#444749'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 2rem
  xxl: 4rem
  container-max: 1440px
  gutter: 24px
  margin-desktop: 48px
  margin-mobile: 16px
---

## Brand & Style

The design system is engineered for a premium tool aggregation platform, targeting professionals who value efficiency, clarity, and cutting-edge technology. The brand personality is authoritative yet unobtrusive, acting as a sophisticated "operating system" for discovering and managing web tools.

The design style merges **Minimalism** with **Glassmorphism**. It utilizes expansive whitespace to reduce cognitive load, while employing frosted glass effects specifically for AI-driven features to signal intelligence and a "premium" layer of service. The emotional response should be one of calm focus and confidence in the platform's technological depth.

## Colors

The palette is rooted in **Deep Professional Blues** and **Clean Whites** to establish trust and a structured environment.

- **Primary (#0F172A):** A deep slate blue used for typography, icons, and core structural elements.
- **Secondary/AI Accent (#6366F1):** An electric indigo reserved for AI-powered features, primary actions, and progress indicators.
- **Surface/Neutral:** A range of subtle grays (from #F8FAFC to #64748B) creates layered depth without introducing visual noise.
- **Success/Warning/Error:** Use muted, professional tones of emerald, amber, and rose to maintain the minimalist aesthetic.

## Typography

This design system uses **Inter** exclusively to achieve a systematic, utilitarian, yet modern feel. 

The typographic hierarchy relies on subtle weight changes and deliberate letter spacing. Headlines use a tighter tracking (-0.01em to -0.02em) to appear more "designed" and premium, while labels use slightly increased tracking and a semi-bold weight to ensure readability at small scales. Line heights are generous (1.5x for body text) to reinforce the airy, minimalist feel.

## Layout & Spacing

The design system utilizes a **12-column fluid grid** for desktop, transitioning to a **4-column grid** for mobile. 

- **Desktop:** 1440px max-width container with 48px outside margins.
- **Rhythm:** An 8px-based spacing system (built on a 4px base unit) ensures vertical consistency.
- **Sidebar:** A fixed 280px navigation sidebar on desktop that collapses into a bottom bar or hamburger menu on mobile.
- **White Space:** Information density should be kept low. Use the `xxl` (64px) spacing unit to separate major sections, allowing the layout to "breathe."

## Elevation & Depth

Depth is conveyed through a combination of **Tonal Layering** and **Ambient Shadows**.

1.  **Level 0 (Background):** Solid #F8FAFC.
2.  **Level 1 (Cards/Sidebar):** White (#FFFFFF) with a very soft, diffused shadow (0px 4px 20px rgba(15, 23, 42, 0.05)).
3.  **Level 2 (Dropdowns/Modals):** White with a more pronounced shadow (0px 10px 30px rgba(15, 23, 42, 0.1)).
4.  **Special Layer (AI Search):** Glassmorphism effect. A backdrop blur of 12px with a 60% transparent white fill and a 1px white border at 20% opacity. This layer always sits atop other elements to emphasize its importance.

## Shapes

The design system follows a **"Rounded"** philosophy to soften the professional blues and create a more approachable user experience.

- **Standard Elements:** Buttons, inputs, and small chips use a 0.5rem (8px) radius.
- **Container Elements:** Tool cards and main content areas use a larger `rounded-xl` (1.5rem / 24px) radius to create the "premium" card-based look requested.
- **AI Elements:** AI-specific components may use pill-shaped (full-round) corners to distinguish them from standard utility components.

## Components

### Buttons
- **Primary:** Solid Indigo (#6366F1) with white text. 8px radius. High-contrast.
- **Secondary:** Transparent with a 1px border of #E2E8F0. 
- **AI Action:** Gradient fill (Indigo to Deep Blue) with a subtle outer glow.

### Cards (Tool Aggregation)
- White background, 24px radius, soft ambient shadow. 
- Hover state: Shadow deepens slightly and the card lifts 2px.
- Internal padding: 24px or 32px to maintain whitespace.

### AI Search Input
- Positioned centrally or as a persistent floating element.
- Glassmorphic surface (Backdrop blur 12px, semi-transparent white).
- Border: 1px subtle white/gray.
- Typography: Body-lg for the input text to emphasize the "conversation" with the AI.

### Navigation Sidebar
- Minimalist. Transparent background with Primary Blue (#0F172A) icons.
- Active state: A subtle vertical bar on the left in Electric Indigo.
- Background: Very light gray (#F1F5F9) or white depending on the layout depth.

### Chips & Tags
- Used for tool categories (e.g., "SaaS", "Design", "DevTools").
- Light gray fill, no border, 12px label text, 8px radius.