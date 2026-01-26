---
description: Frontend design rules and patterns for SQL Agent UI
---

# SQL Agent Frontend Design System

This document defines the established design patterns and rules for the SQL Agent frontend, based on the existing implementation.

## Technology Stack

- **Framework**: React with TypeScript
- **Styling**: TailwindCSS (via `@tailwind` directives in `index.css`)
- **Icons**: Lucide React icons
- **Animations**: Custom CSS keyframes + Tailwind utilities

---

## Color Palette

### Background Colors
- **Primary Background**: `bg-slate-950` (darkest)
- **Secondary Background**: `bg-slate-900` or `bg-slate-900/50` (with transparency)
- **Card/Panel Background**: `bg-slate-900/50` with `backdrop-blur-md`
- **Header Background**: `bg-slate-900/50 backdrop-blur-md`
- **Table Header**: `bg-slate-950`

### Text Colors
- **Primary Text**: `text-slate-200`
- **Secondary Text**: `text-slate-400`
- **Muted Text**: `text-slate-500`, `text-slate-600`
- **White for emphasis**: `text-white`

### Accent Colors by Context
| Context | Primary | Light/Glow | Background | Border |
|---------|---------|------------|------------|--------|
| **Indigo (Default/Primary)** | `bg-indigo-600` | `text-indigo-400`, `text-indigo-300` | `bg-indigo-600/20`, `bg-indigo-500/10` | `border-indigo-500/30` |
| **Emerald (Success/Search)** | `bg-emerald-600` | `text-emerald-400`, `text-emerald-300` | `bg-emerald-500/10` | `border-emerald-500/20` |
| **Amber (Warning/Contributions)** | `bg-amber-600` | `text-amber-400`, `text-amber-300` | `bg-amber-600/20`, `bg-amber-500/10` | `border-amber-500/30` |
| **Purple (Values/Views)** | `bg-purple-600` | `text-purple-400`, `text-purple-300` | `bg-purple-600/20`, `bg-purple-500/20` | `border-purple-500/30` |
| **Red (Error/Danger)** | `bg-red-600` | `text-red-400`, `text-red-300` | `bg-red-500/10` | `border-red-500/30` |
| **Blue (Info/Database)** | `bg-blue-600` | `text-blue-400`, `text-blue-300` | `bg-blue-500/10` | `border-blue-500/30` |
| **Cyan (SQL Display)** | - | `text-cyan-50`, `text-cyan-400` | - | - |
| **Green (Success Toast)** | - | `text-green-400`, `text-green-300` | `bg-green-500/10` | `border-green-500/20` |

---

## Component Patterns

### Buttons

**Primary Action Button (Indigo)**
```tsx
className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
```

**Secondary/Neutral Button**
```tsx
className="flex items-center gap-2 px-4 py-2 bg-slate-800 rounded-lg hover:bg-slate-700 transition text-slate-300"
```

**Danger Button**
```tsx
className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
```

**Icon Button (Contextual)**
```tsx
className="p-2 bg-indigo-500/10 text-indigo-400 rounded hover:bg-indigo-500/20"
```

### Cards & Panels

**Standard Panel**
```tsx
className="bg-slate-900/50 border border-slate-800 rounded-xl p-6"
```

**Info/Guide Panel**
```tsx
className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4"
```

**Status Panels**
- Success: `bg-emerald-500/10 border border-emerald-500/30`
- Error: `bg-red-500/10 border border-red-500/30`
- Warning: `bg-amber-500/10 border border-amber-500/30`
- Info: `bg-blue-500/10 border border-blue-500/30`

### Input Fields

**Text Input**
```tsx
className="w-full bg-slate-800/50 text-slate-200 text-sm placeholder-slate-500 rounded-lg border border-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 px-3 py-2"
```

**Textarea**
```tsx
className="w-full bg-slate-900 border border-slate-700 rounded-lg p-3 text-sm text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none"
```

### Tables

```tsx
// Container
className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden"

// Header
<thead className="bg-slate-950 text-slate-400">

// Body
<tbody className="divide-y divide-slate-800">

// Row hover
<tr className="hover:bg-slate-800/50">

// Cell padding
<td className="p-4">
```

### Modal/Dialog

```tsx
// Overlay
className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm"

// Dialog box
className="bg-slate-900 border border-slate-800 rounded-lg p-6 max-w-md shadow-2xl"
```

---

## Layout Patterns

### Full Screen App Container
```tsx
className="flex h-screen w-screen bg-slate-950 text-slate-200 font-sans"
```

### Sidebar Layout
```tsx
// Sidebar
className="w-64 flex-shrink-0 border-r border-slate-800 bg-slate-900/50 flex flex-col"

// Main content
className="flex-1 overflow-auto bg-slate-950"
```

### Header (Sticky)
```tsx
className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-10"
```

### Footer (Input Area)
```tsx
className="px-6 py-4 bg-slate-900/80 backdrop-blur border-t border-slate-800"
```

---

## Visual Effects

### Glassmorphism
Use `backdrop-blur-md` or `backdrop-blur-sm` with transparent backgrounds:
```tsx
className="bg-slate-900/50 backdrop-blur-md"
```

### Gradient Text
```tsx
className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent"
```

### Glow/Shadow Effects
```tsx
// Button glow
className="shadow-lg shadow-indigo-500/20"

// Card glow (decorative background)
<div className="absolute -inset-1 bg-gradient-to-r from-cyan-500 to-blue-500 rounded-2xl opacity-20 blur"></div>
```

### Status Indicator (Pulsing Dot)
```tsx
<div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
```

---

## Animations

### Custom CSS Keyframes (defined in index.css)

```css
/* Fade in with upward motion */
.animate-fade-in-up {
  animation: fade-in-up 0.5s ease-out;
}

/* Simple fade in */
.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}
```

### Tailwind Animations
- `animate-spin` - Loading spinners
- `animate-pulse` - Status indicators

### Transition Patterns
```tsx
// Standard color/background transitions
className="transition-colors"
className="transition-all"

// Hover with duration
className="transition-all duration-200"
className="transition duration-500"
```

---

## Icon Usage

Import icons from `lucide-react`:
```tsx
import { Send, Loader2, Sparkles, LayoutDashboard, User, Bot, Plus, Trash2, Edit2, Search } from 'lucide-react';
```

### Icon Sizing
- Small (inline): `size={12}` or `size={14}`
- Default: `size={16}` or `size={18}`
- Large (feature): `size={20}` or `size={32}`

### Icon + Text Pattern
```tsx
<button className="flex items-center gap-2">
  <IconName size={18} />
  Button Text
</button>
```

---

## Typography

### Font Family
System UI stack (defined in `:root`):
```css
font-family: system-ui, Avenir, Helvetica, Arial, sans-serif;
```

### Headings
- **Page Title**: `text-2xl font-bold` (often with gradient)
- **Section Title**: `text-lg font-semibold text-white`
- **Subsection**: `text-sm font-semibold text-slate-300`

### Body Text
- **Primary**: `text-slate-200 leading-relaxed`
- **Secondary**: `text-sm text-slate-400`
- **Muted/Helper**: `text-xs text-slate-500` or `text-xs text-slate-600`

### Labels
```tsx
className="text-xs font-semibold text-slate-300 uppercase tracking-wider"
```

### Monospace (Code/SQL)
```tsx
className="font-mono text-sm text-cyan-50"
```

---

## Responsive Patterns

### Grid Layouts
```tsx
className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
```

### Max Width Constraints
```tsx
className="max-w-md"
className="max-w-2xl"
className="max-w-5xl mx-auto"
```

### Truncation
```tsx
className="truncate max-w-md"
```

---

## State Patterns

### Loading State
```tsx
{isLoading && (
  <Loader2 className="animate-spin" size={20} />
)}
```

### Disabled State
```tsx
className="disabled:opacity-50 disabled:cursor-not-allowed"
```

### Active/Selected State
```tsx
// Active navigation item
className={`${currentPage === 'schema' 
  ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/30' 
  : 'text-slate-400 hover:bg-slate-800 hover:text-white'}`}
```

### Empty State
```tsx
<div className="text-center py-8 px-4 text-slate-500 text-sm">
  <IconName size={32} className="mx-auto mb-2 opacity-50" />
  <p>No items found</p>
  <p className="text-xs mt-1">Helpful instruction here</p>
</div>
```

---

## Best Practices

1. **Always use transparency** for overlay backgrounds (e.g., `/50`, `/20`)
2. **Pair backgrounds with matching borders** (e.g., `bg-indigo-600/20` with `border-indigo-500/30`)
3. **Use flex with gap** instead of margins for spacing between elements
4. **Include hover states** for all interactive elements
5. **Add transitions** to all hover/state changes for smooth UX
6. **Use rounded corners** consistently (`rounded-lg`, `rounded-xl`, `rounded-2xl`)
7. **Apply backdrop-blur** for glassmorphism effect on overlays
8. **Icon buttons should have padding** (`p-2`) and consistent sizing
9. **Group related action buttons** with `flex gap-2`
10. **Use semantic color coding** (emerald=success, red=error, amber=warning, blue=info)
