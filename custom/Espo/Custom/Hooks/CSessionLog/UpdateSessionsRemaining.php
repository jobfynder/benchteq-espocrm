<?php

namespace Espo\Custom\Hooks\CSessionLog;

use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

class UpdateSessionsRemaining implements AfterSave
{
    public static int $order = 20;

    public function __construct(
        private EntityManager $entityManager
    ) {}

    /**
     * @param array<string, mixed> $options
     */
    public function afterSave(Entity $entity, array $options): void
    {
        if (!$entity->isAttributeChanged('status')) {
            return;
        }

        $previousStatus = $entity->getFetched('status');
        $currentStatus = $entity->get('status');
        $servicePackageId = $entity->get('servicePackageId');

        if (!$servicePackageId) {
            return;
        }

        $delta = 0;

        if ($previousStatus !== 'Completed' && $currentStatus === 'Completed') {
            $delta = -1;
        } elseif ($previousStatus === 'Completed' && $currentStatus !== 'Completed') {
            $delta = 1;
        }

        if ($delta === 0) {
            return;
        }

        $servicePackage = $this->entityManager->getEntityById(
            'CServicePackage',
            $servicePackageId
        );

        if (!$servicePackage) {
            return;
        }

        $remaining = (int) ($servicePackage->get('sessionsRemaining') ?? 0);
        $total = max(0, (int) ($servicePackage->get('sessionsTotal') ?? 0));
        $remaining = max(0, min($total, $remaining + $delta));

        $servicePackage->set('sessionsRemaining', $remaining);
        $this->entityManager->saveEntity($servicePackage);
    }
}
