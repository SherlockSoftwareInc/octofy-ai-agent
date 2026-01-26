import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ErrorBoundary } from './ErrorBoundary.tsx'

// Component that throws an error for testing
const ThrowError = ({ shouldThrow }: { shouldThrow: boolean }) => {
    if (shouldThrow) {
        throw new Error('Test error')
    }
    return <div>Normal content</div>
}

describe('ErrorBoundary Component', () => {
    // Suppress console.error for error boundary tests
    const originalError = console.error
    beforeEach(() => {
        console.error = vi.fn()
    })

    afterEach(() => {
        console.error = originalError
    })

    it('renders children when there is no error', () => {
        render(
            <ErrorBoundary>
                <div>Test content</div>
            </ErrorBoundary>
        )

        expect(screen.getByText('Test content')).toBeInTheDocument()
    })

    it('renders error UI when child component throws', () => {
        render(
            <ErrorBoundary>
                <ThrowError shouldThrow={true} />
            </ErrorBoundary>
        )

        expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
        expect(screen.getByText(/Test error/)).toBeInTheDocument()
    })

    it('does not catch errors when children render successfully', () => {
        render(
            <ErrorBoundary>
                <ThrowError shouldThrow={false} />
            </ErrorBoundary>
        )

        expect(screen.getByText('Normal content')).toBeInTheDocument()
        expect(screen.queryByText('Something went wrong.')).not.toBeInTheDocument()
    })
})
