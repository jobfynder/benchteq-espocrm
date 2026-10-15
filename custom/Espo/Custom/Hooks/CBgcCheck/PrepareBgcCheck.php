<?php

namespace Espo\Custom\Hooks\CBgcCheck;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Names the record after the customer, so lists read "BGC - Name".
 */
class PrepareBgcCheck implements BeforeSave
{
    public static int $order = 5;

    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->get('name') || !$entity->get('contactId')) {
            return;
        }

        $contact = $this->entityManager->getEntityById('Contact', $entity->get('contactId'));

        if ($contact) {
            $entity->set('name', 'BGC - ' . $contact->get('name'));
        }
    }
}
