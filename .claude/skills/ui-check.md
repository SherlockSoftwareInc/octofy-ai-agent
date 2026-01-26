# Skill: UI Consistency Check

## Purpose
Use this skill whenever I ask you to "Review the UI", "Check the layout", or "Verify frontend changes."

## Workflow

1. **Analyze Tailwind Config:** Check `tailwind.config.js` and `index.css` to ensure color classes match the dark theme palette:
   - Background: `bg-slate-950`, `bg-slate-900/50`
   - Text: `text-slate-200`, `text-white`
   - Accent: `bg-indigo-600`, `text-indigo-400`
   - Error: `border-red-500/50`, `text-red-300`

2. **Layout Audit:** Verify the main layout structure in `App.tsx`:
   - Sidebar (left): Fixed width, scrollable conversation list
   - Main Chat Panel (right): Flex-1, with header/messages/input sections
   - Ensure `overflow-auto` on scrollable containers

3. **Component Consistency:** Check that UI elements follow established patterns:
   - Buttons: `rounded-lg` with hover states (`hover:bg-*`)
   - Cards: `bg-slate-900/50 border border-slate-800 rounded-xl`
   - Icons: Import from `lucide-react`, use consistent sizing

4. **Interactive States:** Verify all interactive elements have:
   - Hover state (`hover:*`)
   - Disabled state (`disabled:opacity-50`)
   - Loading state (show `Loader2` spinner)
   - Focus ring for inputs (`focus:ring-*`)

5. **Chat-Specific Checks:**
   - User messages: Right-aligned with `bg-indigo-900/20`
   - AI messages: Left-aligned with `bg-slate-900/50`
   - Clarification buttons visible when `needsClarification: true`
   - SQL results render in `SQLResultDisplay` component

6. **Console Verification:** Open browser DevTools and confirm:
   - No React warnings or errors
   - No failed network requests to `/api/v1/*`
   - No TypeScript errors during `npm run build`
