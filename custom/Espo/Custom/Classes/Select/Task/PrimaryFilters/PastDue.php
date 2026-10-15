<?php

namespace Espo\Custom\Classes\Select\Task\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

/**
 * Unfinished tasks whose due date has passed.
 */
class PastDue implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where([
            'status!=' => ['Completed', 'Canceled'],
            'dateEnd<' => gmdate('Y-m-d H:i:s'),
        ]);
    }
}
