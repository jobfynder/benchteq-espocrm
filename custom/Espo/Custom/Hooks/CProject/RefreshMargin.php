<?php

namespace Espo\Custom\Hooks\CProject;

use Espo\Core\Hook\Hook\AfterSave;
use Espo\Custom\Classes\ProjectMargin;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Recalculates the margin when the rates or the pay type change.
 */
class RefreshMargin implements AfterSave
{
    public static int $order = 40;

    public function __construct(
        private ProjectMargin $projectMargin
    ) {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        $this->projectMargin->refresh($entity->getId());
    }
}
