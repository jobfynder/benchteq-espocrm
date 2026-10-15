<?php

namespace Espo\Custom\Hooks\CInterviewSession;

use Espo\Core\Hook\Hook\AfterRemove;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\Custom\Classes\CustomerStatus;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps the customer status on the Contact (and Account) up to date.
 */
class RefreshCustomerStatus implements AfterSave, AfterRemove
{
    public static int $order = 20;

    public function __construct(
        private CustomerStatus $customerStatus
    ) {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        $this->refresh($entity);
    }

    public function afterRemove(Entity $entity, RemoveOptions $options): void
    {
        $this->refresh($entity);
    }

    private function refresh(Entity $entity): void
    {
        foreach (array_unique(array_filter([$entity->get('contactId'), $entity->getFetched('contactId')])) as $id) {
            $this->customerStatus->refreshContact($id);
        }
    }
}
