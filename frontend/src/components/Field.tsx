import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { cx } from '../utils/cx'

interface FieldShellProps {
  idPrefix: string
  label: string
  hint?: ReactNode
  error?: string
  required?: boolean
  children: ReactNode
  className?: string
}

function FieldShell({
  idPrefix,
  label,
  hint,
  error,
  required,
  children,
  className,
}: FieldShellProps) {
  return (
    <div className={cx('field', className)}>
      <div className="field__head">
        <label className="field__label" htmlFor={idPrefix}>
          {label}
          {required ? (
            <span className="field__required" aria-hidden="true">
              {' '}
              *
            </span>
          ) : null}
        </label>
      </div>
      {children}
      {hint ? (
        <span className="field__hint" id={`${idPrefix}-hint`}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <p className="field__error" id={`${idPrefix}-error`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

export type TextInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  id?: string
  label: string
  hint?: ReactNode
  error?: string
  required?: boolean
}

export function TextInput({
  id,
  label,
  hint,
  error,
  required,
  className,
  ...rest
}: TextInputProps) {
  const generated = useId()
  const inputId = id ?? generated
  const describedBy =
    [hint ? `${inputId}-hint` : null, error ? `${inputId}-error` : null].filter(Boolean).join(' ') ||
    undefined

  return (
    <FieldShell
      idPrefix={inputId}
      label={label}
      hint={hint}
      error={error}
      required={required}
    >
      <input
        id={inputId}
        className={cx('input', error && 'input--invalid', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        required={required}
        {...rest}
      />
    </FieldShell>
  )
}

export type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & {
  id?: string
  label: string
  hint?: ReactNode
  error?: string
  required?: boolean
}

export function TextArea({
  id,
  label,
  hint,
  error,
  required,
  className,
  rows = 4,
  ...rest
}: TextAreaProps) {
  const generated = useId()
  const areaId = id ?? generated
  const describedBy =
    [hint ? `${areaId}-hint` : null, error ? `${areaId}-error` : null].filter(Boolean).join(' ') ||
    undefined

  return (
    <FieldShell
      idPrefix={areaId}
      label={label}
      hint={hint}
      error={error}
      required={required}
    >
      <textarea
        id={areaId}
        rows={rows}
        className={cx('input', 'input--area', error && 'input--invalid', className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        required={required}
        {...rest}
      />
    </FieldShell>
  )
}

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'onChange'> {
  id?: string
  label: string
  options: SelectOption[]
  placeholder?: string
  hint?: ReactNode
  error?: string
  required?: boolean
  onValueChange: (value: string) => void
}

export function Select({
  id,
  label,
  options,
  placeholder,
  hint,
  error,
  required,
  onValueChange,
  className,
  value,
  ...rest
}: SelectProps) {
  const generated = useId()
  const selectId = id ?? generated
  const describedBy =
    [hint ? `${selectId}-hint` : null, error ? `${selectId}-error` : null].filter(Boolean).join(' ') ||
    undefined

  return (
    <FieldShell
      idPrefix={selectId}
      label={label}
      hint={hint}
      error={error}
      required={required}
    >
      <select
        id={selectId}
        className={cx('select', error && 'input--invalid', className)}
        value={value ?? ''}
        onChange={(event) => onValueChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        required={required}
        {...rest}
      >
        {placeholder ? <option value="">{placeholder}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldShell>
  )
}

interface ToggleProps {
  id?: string
  label: string
  description?: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}

export function Toggle({ id, label, description, checked, onChange, disabled }: ToggleProps) {
  const generated = useId()
  const toggleId = id ?? generated
  return (
    <label className={cx('toggle', disabled && 'toggle--disabled')} htmlFor={toggleId}>
      <input
        id={toggleId}
        type="checkbox"
        role="switch"
        className="toggle__input"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        disabled={disabled}
      />
      <span className="toggle__track" aria-hidden="true">
        <span className="toggle__thumb" />
      </span>
      <span className="toggle__text">
        <span className="toggle__label">{label}</span>
        {description ? <span className="toggle__description">{description}</span> : null}
      </span>
    </label>
  )
}
