import { describe, it, expect, vi } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Toast } from './Toast.tsx'

describe('Toast Component', () => {
    it('renders with success type by default', () => {
        const onClose = vi.fn()
        render(<Toast message="Test message" onClose={onClose} />)

        expect(screen.getByText('Test message')).toBeInTheDocument()
    })

    it('renders with different types', () => {
        const onClose = vi.fn()
        const { rerender } = render(<Toast message="Success" type="success" onClose={onClose} />)
        expect(screen.getByText('Success')).toBeInTheDocument()

        rerender(<Toast message="Error" type="error" onClose={onClose} />)
        expect(screen.getByText('Error')).toBeInTheDocument()

        rerender(<Toast message="Info" type="info" onClose={onClose} />)
        expect(screen.getByText('Info')).toBeInTheDocument()
    })

    it('calls onClose after duration', async () => {
        vi.useFakeTimers()
        const onClose = vi.fn()
        render(<Toast message="Test" duration={1000} onClose={onClose} />)

        expect(onClose).not.toHaveBeenCalled()

        // Fast-forward duration + animation time
        await act(async () => {
            await vi.advanceTimersByTimeAsync(1300)
        })

        expect(onClose).toHaveBeenCalledTimes(1)

        vi.useRealTimers()
    })

    it('closes when X button is clicked', async () => {
        const onClose = vi.fn()
        render(<Toast message="Test" duration={10000} onClose={onClose} />)

        const closeButton = screen.getByRole('button')
        await userEvent.click(closeButton)

        // Wait for animation to complete
        await new Promise(resolve => setTimeout(resolve, 350))

        expect(onClose).toHaveBeenCalled()
    })
})
