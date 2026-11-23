import {
  Boxes,
  Cpu,
  FileText,
  CalendarClock,
  ListTree,
  MapPin,
  Package,
  CreditCard,
  ShoppingCart,
  Star,
  Store,
  User,
  Circle,
} from 'lucide-react'
import { cx } from '../utils/cx'

/** The icon name the backend (ontology/look.py) gives for a kind of thing. */
const MAP: Record<string, typeof User> = {
  order: ShoppingCart,
  person: User,
  product: Package,
  document: FileText,
  payment: CreditCard,
  place: MapPin,
  review: Star,
  store: Store,
  device: Cpu,
  event: CalendarClock,
  line: ListTree,
  thing: Boxes,
}

/** One coloured chip with the thing's icon. Same icon everywhere for a kind. */
export function ThingIcon({
  icon,
  size = 18,
  tint,
  className,
}: {
  icon?: string | null
  size?: number
  /** Wrap in a tinted rounded square (the card/header treatment). */
  tint?: boolean
  className?: string
}) {
  const Icon = (icon && MAP[icon]) || Circle
  if (!tint) return <Icon size={size} aria-hidden="true" className={className} />
  return (
    <span className={cx('thing-icon', className)} aria-hidden="true">
      <Icon size={size} />
    </span>
  )
}
