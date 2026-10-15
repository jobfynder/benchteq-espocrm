<?php

namespace Espo\Custom\Classes\Select\CBgcCheck\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class ReferralDue implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['bgcStatus' => 'Cleared', 'referrerId!=' => null, 'referralPaid' => false]);
    }
}
