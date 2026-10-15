<?php

namespace Espo\Custom\Hooks\CTimesheet;

use Espo\Core\Hook\Hook\AfterRemove;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\Custom\Classes\ProjectMargin;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps the Project margin up to date.
 */
class RefreshProjectMargin implements AfterSave, AfterRemove
{
    public static int $order = 40;

    public function __construct(
        private ProjectMargin $projectMargin
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
        foreach (array_unique(array_filter([$entity->get('projectId'), $entity->getFetched('projectId')])) as $id) {
            $this->projectMargin->refresh($id);
        }
    }
}
