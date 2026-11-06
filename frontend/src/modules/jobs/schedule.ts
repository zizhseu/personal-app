import dayjs from 'dayjs'
import { EVENT_TYPE_LABELS, ROUND_TYPE_LABELS } from './constants.ts'
import { positionLabel } from './selectors.ts'
import type { Application, ScheduleEvent, ScheduleItem } from './types'

function compareStart(left: ScheduleItem, right: ScheduleItem, direction: number): number {
  if (!left.startAt || !right.startAt) return Number(!left.startAt) - Number(!right.startAt)
  return direction * (dayjs(left.startAt).valueOf() - dayjs(right.startAt).valueOf())
}

/** 日程主时间始终采用开始时间，截止时间单独用于期限判断。 */
export function createScheduleGroups(applications: Application[], events: ScheduleEvent[], now = Date.now()) {
  const items: ScheduleItem[] = []
  for (const application of applications) {
    for (const round of application.rounds) {
      if (round.roundType === 'screening' || (!round.startAt && !round.scheduledAt)) continue
      items.push({
        key: `round-${round.id}`,
        kind: 'round',
        startAt: round.startAt,
        deadlineAt: round.scheduledAt,
        time: round.startAt ? dayjs(round.startAt).format('MM-DD HH:mm') : '开始时间待补充',
        typeLabel: ROUND_TYPE_LABELS[round.roundType],
        title: `${application.company} · ${positionLabel(round.position)}`,
        location: null,
        round,
        applicationId: application.id,
      })
    }
  }
  for (const event of events) {
    items.push({
      key: `event-${event.id}`,
      kind: 'event',
      startAt: event.eventTime,
      deadlineAt: null,
      time: dayjs(event.eventTime).format('MM-DD HH:mm'),
      typeLabel: EVENT_TYPE_LABELS[event.eventType],
      title: event.title,
      location: event.location,
      event,
      applicationId: event.applicationId,
    })
  }

  const todo: ScheduleItem[] = []
  const done: ScheduleItem[] = []
  const expired: ScheduleItem[] = []
  for (const item of items) {
    if (item.kind === 'event') {
      const target = dayjs(item.startAt).valueOf() >= now ? todo : done
      target.push(item)
    } else if (item.round!.result !== 'not_started') {
      done.push(item)
    } else {
      const limit = item.deadlineAt ?? item.startAt
      const target = dayjs(limit).valueOf() >= now ? todo : expired
      target.push(item)
    }
  }
  todo.sort((left, right) => compareStart(left, right, 1))
  done.sort((left, right) => compareStart(left, right, -1))
  expired.sort((left, right) => compareStart(left, right, -1))
  return { todo, done, expired }
}
