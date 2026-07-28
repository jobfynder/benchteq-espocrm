<?php

namespace Espo\Custom\Hooks\CServicePackage;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;

class ValidateProviderAssignment implements BeforeSave
{
    public static int $order = 10;

    private const SERVICE_MAP = [
        'Interview Support' => 'Interview Supporter',
        'Job Support' => 'Freelancer',
        'BGC' => 'BGC Verification',
    ];

    public function __construct(
        private EntityManager $entityManager
    ) {}

    /**
     * @throws BadRequest
     */
    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $serviceType = (string) ($entity->get('serviceType') ?? '');
        $providerId = $entity->get('fulfillingProviderId');
        $deliveryResourceId = $entity->get('primaryDeliveryResourceId');

        if ($serviceType === 'BGC' && !$providerId) {
            throw new BadRequest('A fulfilling Provider is required for BGC.');
        }

        if ($providerId) {
            $this->validateProviderService((string) $providerId, $serviceType);
        }

        if ($serviceType === 'BGC' || !$deliveryResourceId) {
            return;
        }

        $deliveryResource = $this->entityManager->getEntityById(
            'CDeliveryResource',
            (string) $deliveryResourceId
        );

        if (!$deliveryResource) {
            throw new BadRequest('The selected Delivery Resource does not exist.');
        }

        if ($deliveryResource->get('sourcedVia') !== 'Via Provider') {
            return;
        }

        if (!$providerId) {
            throw new BadRequest(
                'Select the Provider that supplied this Delivery Resource.'
            );
        }

        if ($deliveryResource->get('providerId') !== $providerId) {
            throw new BadRequest(
                'The Provider must match the selected Delivery Resource.'
            );
        }
    }

    /**
     * @throws BadRequest
     */
    private function validateProviderService(
        string $providerId,
        string $serviceType
    ): void {
        $provider = $this->entityManager->getEntityById(
            'CProvider',
            $providerId
        );

        if (!$provider) {
            throw new BadRequest('The selected Provider does not exist.');
        }

        $requiredService = self::SERVICE_MAP[$serviceType] ?? null;
        $services = $provider->get('servicesSupplied');

        if (
            $requiredService &&
            (
                !is_array($services) ||
                !in_array($requiredService, $services, true)
            )
        ) {
            throw new BadRequest(
                "The selected Provider does not supply {$requiredService}."
            );
        }
    }
}
