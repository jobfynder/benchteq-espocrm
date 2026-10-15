<?php

namespace Espo\Custom\Jobs;

use Espo\Core\Job\JobDataLess;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Runs every hour. Sends a CRM notification (the bell) for:
 *  - an Interview in the next 24 hours with no freelancer,
 *  - an Interview in the next 24 hours: time to confirm with the customer and freelancer,
 *  - a Lead whose next follow-up date has come.
 * Each alert is sent once.
 */
class SendAlerts implements JobDataLess
{
    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function run(): void
    {
        $managers = $this->interviewManagerIds();
        $now = gmdate('Y-m-d H:i:s');
        $soon = gmdate('Y-m-d H:i:s', time() + 24 * 3600);

        $interviews = $this->entityManager->getRDBRepository('CInterviewSession')
            ->where(['status' => 'Planned', 'dateStart>=' => $now, 'dateStart<=' => $soon])
            ->find();

        foreach ($interviews as $interview) {
            $link = '[' . $interview->get('name') . '](#CInterviewSession/view/' . $interview->getId() . ')';
            $people = $this->unique(array_merge([$interview->get('assignedUserId')], $managers));

            if (!$interview->get('freelancerId')) {
                if (!$interview->get('noFreelancerAlertSent')) {
                    $this->notify($people, 'No freelancer yet for an interview in the next 24 hours: ' . $link,
                        'CInterviewSession', $interview->getId());
                    $this->flag($interview, 'noFreelancerAlertSent');
                }

                continue;
            }

            if (!$interview->get('reminderSent')) {
                $this->notify($people, 'Interview in the next 24 hours. Confirm the time with the customer '
                    . 'and the freelancer: ' . $link, 'CInterviewSession', $interview->getId());
                $this->flag($interview, 'reminderSent');
            }
        }

        $today = gmdate('Y-m-d');

        $leads = $this->entityManager->getRDBRepository('Lead')
            ->where([
                'nextFollowUpDate<=' => $today,
                'status!=' => ['Converted', 'Dead', 'Recycled'],
                'OR' => [['followUpAlertDate' => null], ['followUpAlertDate!=' => $today]],
            ])
            ->find();

        foreach ($leads as $lead) {
            $link = '[' . $lead->get('name') . '](#Lead/view/' . $lead->getId() . ')';
            $people = $this->unique([$lead->get('assignedUserId')]);

            $this->notify($people, 'Lead follow-up is due: ' . $link, 'Lead', $lead->getId());
            $lead->set('followUpAlertDate', $today);
            $this->entityManager->saveEntity($lead, ['silent' => true, 'skipHooks' => true]);
        }
    }

    /** @return string[] */
    private function interviewManagerIds(): array
    {
        try {
            $users = $this->entityManager->getRDBRepository('User')
                ->join('roles')
                ->where(['roles.name' => 'Interview Manager', 'isActive' => true])
                ->find();
        } catch (Throwable) {
            return [];
        }

        $ids = [];

        foreach ($users as $user) {
            $ids[] = $user->getId();
        }

        return $ids;
    }

    /**
     * @param array<int, ?string> $ids
     * @return string[]
     */
    private function unique(array $ids): array
    {
        return array_values(array_unique(array_filter($ids)));
    }

    /** @param string[] $userIds */
    private function notify(array $userIds, string $message, string $type, string $id): void
    {
        foreach ($userIds as $userId) {
            $notification = $this->entityManager->getNewEntity('Notification');
            $notification->set([
                'type' => 'Message',
                'userId' => $userId,
                'message' => $message,
                'relatedType' => $type,
                'relatedId' => $id,
            ]);
            $this->entityManager->saveEntity($notification);
        }
    }

    private function flag(Entity $entity, string $field): void
    {
        $entity->set($field, true);
        $this->entityManager->saveEntity($entity, ['silent' => true, 'skipHooks' => true]);
    }
}
