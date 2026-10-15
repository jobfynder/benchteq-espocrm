<?php

namespace Espo\Custom\Hooks\CTimesheet;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Calculates hours from the start and end time, and fills the freelancer and
 * coordinator from the Project when they are empty. Keeps the Project link in step with
 * the Package so a Project can list its timesheets.
 */
class PrepareTimesheet implements BeforeSave
{
    public static int $order = 5;

    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (
            $entity->isNew() ||
            $entity->isAttributeChanged('dateStart') ||
            $entity->isAttributeChanged('dateEnd')
        ) {
            $entity->set('hours', $this->calculateHours($entity));
        }

        $project = $this->getProject($entity->get('paymentBlockId'));

        if ($project && $entity->get('projectId') !== $project->getId()) {
            $entity->set('projectId', $project->getId());
        }

        if ($entity->get('freelancerId') && $entity->get('assignedUserId')) {
            return;
        }

        if (!$project) {
            return;
        }

        if (!$entity->get('freelancerId') && $project->get('freelancerId')) {
            $entity->set('freelancerId', $project->get('freelancerId'));
        }

        if (!$entity->get('assignedUserId') && $project->get('assignedUserId')) {
            $entity->set('assignedUserId', $project->get('assignedUserId'));
        }
    }

    private function calculateHours(Entity $entity): float
    {
        $start = $entity->get('dateStart');
        $end = $entity->get('dateEnd');

        if (!$start || !$end) {
            return 0.0;
        }

        $seconds = strtotime($end . ' UTC') - strtotime($start . ' UTC');

        return $seconds > 0 ? round($seconds / 3600, 2) : 0.0;
    }

    private function getProject(?string $paymentBlockId): ?Entity
    {
        if (!$paymentBlockId) {
            return null;
        }

        $block = $this->entityManager->getEntityById('CPaymentBlock', $paymentBlockId);

        if (!$block || !$block->get('projectId')) {
            return null;
        }

        return $this->entityManager->getEntityById('CProject', $block->get('projectId'));
    }
}
