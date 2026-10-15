<?php

namespace Espo\Custom\Classes\Select\Task\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

/**
 * Open tasks that are past their due date and marked High or Urgent.
 */
class OverdueCritical implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where([
            'status!=' => ['Completed', 'Canceled'],
            'dateEnd<' => gmdate('Y-m-d H:i:s'),
            'priority' => ['High', 'Urgent'],
        ]);
    }
}
