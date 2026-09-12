import request from '@/shared/api/request'
import type { Application, ApplicationPayload, RoundPayload, ScheduleEvent, EventPayload } from './types'

/** jobs 模块全部接口调用 */

export function fetchApplications(): Promise<Application[]> {
  return request.get('/jobs/applications') as Promise<Application[]>
}

export function fetchApplication(id: number): Promise<Application> {
  return request.get(`/jobs/applications/${id}`) as Promise<Application>
}

export function createApplication(payload: ApplicationPayload): Promise<Application> {
  return request.post('/jobs/applications', payload) as Promise<Application>
}

export function updateApplication(
  id: number,
  payload: Partial<ApplicationPayload>,
): Promise<Application> {
  return request.put(`/jobs/applications/${id}`, payload) as Promise<Application>
}

export function patchStatus(id: number, status: Application['status']): Promise<Application> {
  return request.patch(`/jobs/applications/${id}/status`, { status }) as Promise<Application>
}

export function patchOfferDecision(
  id: number,
  offerDecision: 'accepted' | 'rejected_offer',
): Promise<Application> {
  return request.patch(`/jobs/applications/${id}/offer-decision`, {
    offerDecision,
  }) as Promise<Application>
}

export function deleteApplication(id: number): Promise<void> {
  return request.delete(`/jobs/applications/${id}`) as Promise<void>
}

export function createRound(
  applicationId: number,
  payload: RoundPayload,
): Promise<Application['rounds'][number]> {
  return request.post(
    `/jobs/applications/${applicationId}/rounds`,
    payload,
  ) as Promise<Application['rounds'][number]>
}

export function updateRound(
  roundId: number,
  payload: Partial<RoundPayload>,
): Promise<Application['rounds'][number]> {
  return request.put(
    `/jobs/rounds/${roundId}`,
    payload,
  ) as Promise<Application['rounds'][number]>
}

export function deleteRound(roundId: number): Promise<void> {
  return request.delete(`/jobs/rounds/${roundId}`) as Promise<void>
}

export function fetchEvents(): Promise<ScheduleEvent[]> {
  return request.get('/jobs/events') as Promise<ScheduleEvent[]>
}

export function createEvent(payload: EventPayload): Promise<ScheduleEvent> {
  return request.post('/jobs/events', payload) as Promise<ScheduleEvent>
}

export function updateEvent(id: number, payload: Partial<EventPayload>): Promise<ScheduleEvent> {
  return request.put(`/jobs/events/${id}`, payload) as Promise<ScheduleEvent>
}

export function deleteEvent(id: number): Promise<void> {
  return request.delete(`/jobs/events/${id}`) as Promise<void>
}